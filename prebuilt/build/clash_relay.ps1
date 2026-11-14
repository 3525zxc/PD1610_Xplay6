# Clash Verge 局域网转发器（PD1610 编译专用）
# 作用：Clash Verge 只监听 127.0.0.1:7897，WSL2(NAT) 无法直接使用。
#       本脚本监听 0.0.0.0:7890，把 TCP 流量原样转发到 127.0.0.1:7897，
#       使 WSL 可通过 172.31.96.1:7890 借用 Windows 上的代理。
# 约束：仅接受来自 WSL 私网网段 (172.16.0.0/12, 10.0.0.0/8, 192.168.0.0/16) 的连接，
#       避免把代理暴露给不可控来源。

param(
    [int]$ListenPort = 7890,
    [int]$TargetPort = 7897,
    [string]$TargetHost = '127.0.0.1'
)

$src = @'
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;

public class ClashRelay
{
    static int listenPort;
    static string targetHost;
    static int targetPort;

    public static void Start(int lp, string th, int tp)
    {
        listenPort = lp; targetHost = th; targetPort = tp;
        var listener = new TcpListener(IPAddress.Any, listenPort);
        listener.Start(128);
        Console.WriteLine("relay listening 0.0.0.0:" + listenPort + " -> " + targetHost + ":" + targetPort);
        while (true)
        {
            TcpClient c;
            try { c = listener.AcceptTcpClient(); }
            catch { continue; }
            var t = new Thread(Handle);
            t.IsBackground = true;
            t.Start(c);
        }
    }

    static bool Allowed(IPEndPoint ep)
    {
        if (ep == null) return false;
        var b = ep.Address.GetAddressBytes();
        if (b.Length != 4) return true;              // IPv6 本机回环，放行
        if (b[0] == 127) return true;
        if (b[0] == 10) return true;
        if (b[0] == 192 && b[1] == 168) return true;
        if (b[0] == 172 && b[1] >= 16 && b[1] <= 31) return true;
        return false;
    }

    static void Handle(object state)
    {
        var client = (TcpClient)state;
        TcpClient server = null;
        try
        {
            var ep = client.Client.RemoteEndPoint as IPEndPoint;
            if (!Allowed(ep)) { client.Close(); return; }
            server = new TcpClient();
            server.Connect(targetHost, targetPort);
            server.NoDelay = true;
            client.NoDelay = true;
            var cs = client.GetStream();
            var ss = server.GetStream();
            Pump(cs, ss, client, server);
            Pump(ss, cs, server, client);
        }
        catch
        {
            try { client.Close(); } catch { }
            try { if (server != null) server.Close(); } catch { }
        }
    }

    static void Pump(NetworkStream from, NetworkStream to, TcpClient ownerFrom, TcpClient ownerTo)
    {
        var t = new Thread(() =>
        {
            var buf = new byte[32768];
            try
            {
                int n;
                while ((n = from.Read(buf, 0, buf.Length)) > 0)
                {
                    to.Write(buf, 0, n);
                    to.Flush();
                }
            }
            catch { }
            finally
            {
                try { to.Close(); } catch { }
                try { ownerFrom.Close(); } catch { }
                try { ownerTo.Close(); } catch { }
            }
        });
        t.IsBackground = true;
        t.Start();
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp
[ClashRelay]::Start($ListenPort, $TargetHost, $TargetPort)
