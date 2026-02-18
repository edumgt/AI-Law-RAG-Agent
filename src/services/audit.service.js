function audit(db, { userId = null, clientId = null, eventType, payload = {} }) {
  db.prepare(
    "INSERT INTO audit_events (user_id, client_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)"
  ).run(
    userId,
    clientId,
    eventType,
    JSON.stringify(payload),
    new Date().toISOString()
  );
}

function recentAudits(db, limit = 50) {
  return db.prepare(
    "SELECT id, user_id, client_id, event_type, payload_json, created_at FROM audit_events ORDER BY id DESC LIMIT ?"
  ).all(limit).map(r => ({
    id: r.id,
    userId: r.user_id,
    clientId: r.client_id,
    eventType: r.event_type,
    payload: JSON.parse(r.payload_json),
    createdAt: r.created_at,
  }));
}

module.exports = { audit, recentAudits };
