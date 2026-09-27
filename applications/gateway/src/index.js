const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const promClient = require('prom-client');

const app = express();
const PORT = process.env.PORT || 8080;

const register = new promClient.Registry();
promClient.collectDefaultMetrics({ register });

const requestCounter = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP Requests',
  labelNames: ['method', 'endpoint', 'http_status'],
  registers: [register]
});

const requestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP Request Latency',
  labelNames: ['method', 'endpoint'],
  registers: [register]
});

// CORS Middleware
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-Request-ID');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Structured Logging & Prometheus Metrics
app.use((req, res, next) => {
  const start = Date.now();
  const requestId = req.headers['x-request-id'] || `req-${Math.random().toString(36).substr(2, 9)}`;
  req.headers['x-request-id'] = requestId;

  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    if (req.path !== '/metrics' && req.path !== '/health' && req.path !== '/ready' && req.path !== '/healthz') {
      requestCounter.labels(req.method, req.path, res.statusCode).inc();
      requestDuration.labels(req.method, req.path).observe(duration);
    }

    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      service: 'gateway',
      level: 'INFO',
      request_id: requestId,
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_seconds: parseFloat(duration.toFixed(4)),
      message: `${req.method} ${req.path} responded ${res.statusCode} in ${duration.toFixed(4)}s`
    }));
  });
  next();
});

// Microservice Reverse Proxies
const createServiceProxy = (targetUrl, pathPrefix) => {
  return createProxyMiddleware({
    target: targetUrl,
    changeOrigin: true,
    pathRewrite: { [`^${pathPrefix}`]: '' },
    onError: (err, req, res) => {
      console.error(`Proxy error for ${req.path} -> ${targetUrl}:`, err.message);
      res.status(502).json({
        error: 'Bad Gateway',
        message: `Unable to reach upstream microservice for ${req.path}`,
        service_target: targetUrl,
        timestamp: new Date().toISOString()
      });
    }
  });
};

app.use('/api/v1/auth', createServiceProxy(process.env.AUTH_SERVICE_URL || 'http://auth-service:8000', '/api/v1/auth'));
app.use('/api/v1/users', createServiceProxy(process.env.USERS_SERVICE_URL || 'http://users-service:8000', '/api/v1/users'));
app.use('/api/v1/products', createServiceProxy(process.env.PRODUCTS_SERVICE_URL || 'http://products-service:8000', '/api/v1/products'));
app.use('/api/v1/orders', createServiceProxy(process.env.ORDERS_SERVICE_URL || 'http://orders-service:8000', '/api/v1/orders'));
app.use('/api/v1/payment', createServiceProxy(process.env.PAYMENT_SERVICE_URL || 'http://payment-service:8000', '/api/v1/payment'));
app.use('/api/v1/notification', createServiceProxy(process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:8000', '/api/v1/notification'));

// Health & Telemetry Checkpoints
app.get('/health', (req, res) => res.json({ status: 'healthy', service: 'gateway', version: '1.0.0' }));
app.get('/healthz', (req, res) => res.json({ status: 'healthy', service: 'gateway' }));
app.get('/ready', (req, res) => res.json({ status: 'ready', service: 'gateway' }));
app.get('/version', (req, res) => res.json({ version: '1.0.0', service: 'gateway' }));
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

app.listen(PORT, () => {
  console.log(`Enterprise API Gateway proxy running on port ${PORT}`);
});