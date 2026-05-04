# network_monitor.py
import psutil
import time
import sys
from datetime import datetime

def find_wechat_cli_processes():
    """查找所有 wechat-cli 相关进程"""
    targets = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline:
                cmdline_str = ' '.join(cmdline).lower()
                if 'wechat-cli' in cmdline_str or 'wechat_cli' in cmdline_str:
                    targets.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return targets


def get_network_connections(proc):
    """获取指定进程的网络连接"""
    connections = []
    try:
        # 获取 TCP 和 UDP 连接
        for conn in proc.connections(kind='inet'):
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "未知"
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "未知"
            connections.append({
                'type': 'TCP' if conn.type == 'tcp' else 'UDP',
                'local': laddr,
                'remote': raddr,
                'status': conn.status
            })
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return connections


def monitor(target_pids):
    """监控指定 PID 列表的进程网络行为"""
    watched = set(target_pids)
    known_connections = set()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始监控 {len(watched)} 个 wechat-cli 进程...")
    print("按 Ctrl+C 停止监控\n")

    try:
        while True:
            current_pids = set()
            for pid in watched.copy():
                try:
                    proc = psutil.Process(pid)
                    current_pids.add(pid)
                    conns = get_network_connections(proc)
                    for c in conns:
                        # 忽略常见的本机回环连接 (127.0.0.1) 和某些系统端口
                        if c['remote'].startswith('127.'):
                            continue
                        if c['remote'] == '0.0.0.0:0':
                            continue

                        conn_key = f"{pid}:{c['remote']}"
                        if conn_key not in known_connections:
                            known_connections.add(conn_key)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 检测到网络连接!")
                            print(f"  PID: {pid}")
                            print(f"  协议: {c['type']}")
                            print(f"  本地地址: {c['local']}")
                            print(f"  远程地址: {c['remote']}")
                            print(f"  状态: {c['status']}")
                            print("-" * 50)
                except psutil.NoSuchProcess:
                    watched.discard(pid)

            if not watched:
                print("所有 wechat-cli 进程已退出，监控结束。")
                break

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n监控已停止。")
        if known_connections:
            print(f"共检测到 {len(known_connections)} 次可疑网络连接。")
        else:
            print("✅ 未检测到任何对外网络连接，wechat-cli 是安全的。")


if __name__ == "__main__":
    # 查找当前运行的 wechat-cli 进程
    processes = find_wechat_cli_processes()
    if not processes:
        print("未检测到正在运行的 wechat-cli 进程。")
        print("请先在另一个命令行窗口运行 wechat-cli 命令，然后再启动本监控脚本。")
        sys.exit(1)

    print(f"发现 {len(processes)} 个相关进程:")
    for proc in processes:
        print(f"  PID: {proc.pid}, 名称: {proc.name()}")
    print()

    pids = [p.pid for p in processes]
    monitor(pids)