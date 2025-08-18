const express = require('express');
const path = require('path');

// Config
const PORT = parseInt(process.env.DAPR_APP_PORT || '5200', 10);
const PUBSUB_NAME = process.env.DAPR_PUBSUB_NAME || 'pubsub';
const BROADCAST_TOPIC = process.env.DAPR_BROADCAST_TOPIC || 'beacon_channel';

const app = express();
// Parse JSON and CloudEvents content types
app.use(express.json({ limit: '2mb', type: [ 'application/json', 'application/*+json' ] }));

// In-memory SSE subscribers
const clients = new Set();

function broadcast(event) {
  const payload = `data: ${JSON.stringify(event)}\n\n`;
  for (const res of clients) {
    try {
      res.write(payload);
    } catch (e) {
      // Best-effort; drop dead clients
      try { res.end(); } catch {}
      clients.delete(res);
    }
  }
}

// Dapr subscription discovery endpoint
app.get('/dapr/subscribe', (_req, res) => {
  res.json([
    { pubsubname: PUBSUB_NAME, topic: BROADCAST_TOPIC, route: 'beacon_channel' },
  ]);
});

// Topic handler: receives CloudEvents from Dapr pub/sub
app.post('/beacon_channel', (req, res) => {
  const ce = req.body || {};
  const time = ce.time || new Date().toISOString();
  const source = ce.source || 'unknown';
  let data = ce.data;

  // If data is a JSON string, try to parse
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch { /* keep as string */ }
  }

  let content = undefined;
  if (data && typeof data === 'object') {
    content = data.content ?? data.message ?? data.text ?? data;
  } else if (typeof data === 'string') {
    content = data;
  } else {
    content = {};
  }

  const event = { time, source, content };
  console.log(`[web-monitor] ${source}:`, typeof content === 'string' ? content : JSON.stringify(content));
  broadcast(event);
  res.sendStatus(200);
});

// SSE endpoint for browser clients
app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders?.();

  res.write(': connected\n\n');

  clients.add(res);
  const keepAlive = setInterval(() => {
    try { res.write(': ping\n\n'); } catch { /* noop */ }
  }, 25000);

  req.on('close', () => {
    clearInterval(keepAlive);
    clients.delete(res);
    try { res.end(); } catch { /* noop */ }
  });
});

// Static SPA
const staticDir = path.join(__dirname, 'public');
app.use(express.static(staticDir));
app.get('/', (_req, res) => {
  res.sendFile(path.join(staticDir, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`[web-monitor] listening on 0.0.0.0:${PORT} | topic=${BROADCAST_TOPIC} pubsub=${PUBSUB_NAME}`);
});
