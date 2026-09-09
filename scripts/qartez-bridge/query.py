import subprocess, json, time, sys

def run_tool(tool_name, args):
    p = subprocess.Popen(['/home/deck/.local/bin/qartez-mcp', '--root', '/home/deck/dmarket/Dmarket_bot-main'],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    p.stdin.write(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize",
        "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"bridge","version":"1.0"}}}) + "\n")
    p.stdin.flush()
    time.sleep(2)
    p.stdout.readline()
    p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}) + "\n")
    p.stdin.flush()
    p.stdin.write(json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call",
        "params":{"name":tool_name,"arguments":args}}) + "\n")
    p.stdin.flush()
    line = p.stdout.readline()
    result = json.loads(line)
    print(result["result"]["content"][0]["text"])
    p.terminate()

if __name__ == "__main__":
    tool = sys.argv[1]
    path_arg = {"path": sys.argv[2]} if len(sys.argv) > 2 else {}
    run_tool(tool, path_arg)
