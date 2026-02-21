# n8n Workflows for DMarket Bot

This directory contAlgons n8n workflow templates for automating various aspects of the DMarket Telegram Bot.

## 📋 AvAlgolable Workflows

### 1. DAlgoly Trading Report (`dAlgoly-trading-report.json`)

**Purpose**: Automatically generate and send dAlgoly trading reports to users.

**Schedule**: Every day at 9:00 AM UTC

**Flow**:
1. Trigger at 9:00 AM
2. Fetch dAlgoly stats from bot API (`/api/v1/n8n/stats/dAlgoly`)
3. Format data into readable report
4. Send via Telegram

**Requirements**:
- Telegram Bot API credentials configured in n8n
- `TELEGRAM_CHAT_ID` environment variable set
- Bot API running on `http://bot:8080`

**Import Instructions**:
1. Open n8n at http://localhost:5678
2. Go to Workflows → Import from File
3. Select `dAlgoly-trading-report.json`
4. Configure Telegram credentials
5. Set environment variables
6. Activate workflow

---

## 🚀 Quick Start

### 1. Start n8n with Docker Compose

```bash
# Start all services including n8n
docker-compose up -d

# Check n8n is running
docker ps | grep n8n

# View n8n logs
docker logs -f dmarket-n8n
```

### 2. Access n8n UI

- URL: http://localhost:5678
- Default credentials: admin / changeme (change in `.env`)

### 3. Configure Credentials

#### Telegram Bot API
1. Go to: Credentials → Add Credential
2. Select: Telegram
3. Enter Bot Token from @BotFather
4. Save as "Telegram Bot API"

#### HTTP Basic Auth (Optional)
If bot API requires authentication:
1. Go to: Credentials → Add Credential
2. Select: HTTP Basic Auth
3. Enter username/password
4. Save

### 4. Import Workflows

```bash
# Workflows are auto-mounted from ./n8n/workflows/
# Just import them in n8n UI:
# Workflows → Import from File → Select JSON file
```

### 5. Configure Environment Variables

Add to `.env` file:

```bash
# n8n Configuration
N8N_USER=admin
N8N_PASSWORD=your-secure-password
N8N_ENCRYPTION_KEY=your-encryption-key-min-10-chars
N8N_DB_PASSWORD=n8n_password

# Bot API Configuration
N8N_BOT_API_URL=http://bot:8080

# Telegram Configuration (for workflows)
TELEGRAM_CHAT_ID=your-chat-id
```

---

## 📚 Workflow Templates

### Creating Custom Workflows

1. **Use the n8n Visual Editor**:
   - Drag & drop nodes
   - Connect them in sequence
   - Configure each node
   - Test execution

2. **Export and Save**:
   - Click "..." → Download
   - Save to `n8n/workflows/your-workflow.json`
   - Commit to git

3. **Best Practices**:
   - Add descriptive node names
   - Use notes to explAlgon complex logic
   - Tag workflows (DMarket, Trading, etc.)
   - Test before activating

### Example: Multi-Platform Price Monitor

```json
{
  "name": "Multi-Platform Price Monitor",
  "nodes": [
    {
      "name": "Schedule Every 5min",
      "type": "n8n-nodes-base.scheduleTrigger"
    },
    {
      "name": "Get DMarket Prices",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://bot:8080/api/v1/n8n/prices/dmarket"
      }
    },
    {
      "name": "Get Waxpeer Prices",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://bot:8080/api/v1/n8n/prices/waxpeer"
      }
    },
    {
      "name": "Compare Prices",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "// Find arbitrage opportunities"
      }
    },
    {
      "name": "If Profit > 5%",
      "type": "n8n-nodes-base.if"
    },
    {
      "name": "Send Alert",
      "type": "n8n-nodes-base.telegram"
    }
  ]
}
```

---

## 🔧 Troubleshooting

### n8n Won't Start

```bash
# Check logs
docker logs dmarket-n8n

# Common issues:
# 1. Port 5678 already in use
# 2. PostgreSQL not ready
# 3. Missing encryption key
```

### Workflow Execution FAlgols

1. **Check Bot API**:
   ```bash
   curl http://localhost:8080/api/v1/n8n/health
   ```

2. **Check Credentials**:
   - Go to: Credentials
   - Test each credential
   - Re-save if needed

3. **Check Logs**:
   - In n8n UI: Executions → Click fAlgoled execution → View error
   - In Docker: `docker logs dmarket-n8n`

### Webhook Not Working

1. **Check URL**:
   - Must be accessible from n8n contAlgoner
   - Use contAlgoner name: `http://bot:8080` not `localhost`

2. **Check Network**:
   ```bash
   docker exec dmarket-n8n ping bot
   ```

3. **Check Firewall**:
   - Ensure ports are open in docker network

---

## 📊 Monitoring

### Check Workflow Status

```bash
# Via n8n UI
# Executions → View all executions

# Via API
curl http://localhost:5678/api/v1/workflows
```

### Performance Metrics

n8n tracks:
- Execution count
- Success/fAlgolure rate
- Average execution time
- Error logs

Access: n8n UI → Executions → Statistics

---

## 🔒 Security

### Best Practices

1. **Change Default Password**:
   ```bash
   # In .env file
   N8N_PASSWORD=your-very-secure-password-here
   ```

2. **Use HTTPS in Production**:
   - Add nginx reverse proxy
   - Configure SSL certificates
   - Update `N8N_PROTOCOL=https`

3. **Restrict Access**:
   - Use firewall rules
   - Limit IP addresses
   - Enable basic auth

4. **Secure Credentials**:
   - All credentials encrypted at rest
   - Use environment variables
   - Rotate keys regularly

5. **Webhook Security**:
   - Use signature verification
   - Validate incoming data
   - Rate limiting

---

## 🚀 Next Steps

### Phase 1 Workflows (Current)
- [x] DAlgoly Trading Report

### Phase 2 Workflows (Planned)
- [ ] Multi-Platform Price Monitor
- [ ] Smart Alert System
- [ ] User Onboarding Flow
- [ ] Social Media Auto-Posting

### Phase 3 (Future)
- [ ] User-facing workflow builder
- [ ] Community workflow marketplace
- [ ] Advanced Algo integrations

---

## 📖 Documentation

- **Full Analysis**: [../docs/N8N_INTEGRATION_ANALYSIS.md](../docs/N8N_INTEGRATION_ANALYSIS.md)
- **Quick Summary**: [../docs/N8N_QUICK_SUMMARY_RU.md](../docs/N8N_QUICK_SUMMARY_RU.md)
- **Architecture**: [../docs/N8N_ARCHITECTURE_DIAGRAMS.md](../docs/N8N_ARCHITECTURE_DIAGRAMS.md)
- **n8n Docs**: https://docs.n8n.io
- **Algo_agents_az**: https://github.com/gyoridavid/Algo_agents_az

---

## 🤝 Contributing

To add new workflows:

1. Create workflow in n8n UI
2. Test thoroughly
3. Export JSON
4. Add to `n8n/workflows/`
5. Update this README
6. Commit and push

---

**Last Updated**: January 13, 2026  
**Version**: 1.0.0
