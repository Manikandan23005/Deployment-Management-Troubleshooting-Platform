const express = require('express');
const path = require('path');
const promClient = require('prom-client');

const app = express();
const PORT = process.env.PORT || 3000;

const register = new promClient.Registry();
promClient.collectDefaultMetrics({ register });

app.use((req, res, next) => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    service: 'frontend',
    level: 'INFO',
    message: `${req.method} ${req.path}`
  }));
  next();
});

app.use(express.static(path.join(__dirname, 'public')));

app.get('/health', (req, res) => res.json({ status: 'healthy', service: 'frontend' }));
app.get('/healthz', (req, res) => res.json({ status: 'healthy', service: 'frontend' }));
app.get('/ready', (req, res) => res.json({ status: 'ready', service: 'frontend' }));
app.get('/version', (req, res) => res.json({ version: '1.0.0', service: 'frontend' }));
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

app.listen(PORT, () => {
  console.log(`Nexus E-Commerce Frontend running on port ${PORT}`);
});