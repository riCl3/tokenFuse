"""Local webhook receiver for testing burn-rate alerts.

Prints every alert POST it receives to stdout so you can confirm an alert was
delivered without setting up Telegram.

Run:  .venv\\Scripts\\python.exe scripts\\webhook_receiver.py
Then point the proxy at it with  ALERT_WEBHOOK_URL=http://127.0.0.1:8300/alert
"""

import uvicorn
from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/alert")
async def alert(request: Request):
    body = await request.json()
    print("=== ALERT RECEIVED ===")
    print(body.get("text", ""))
    print("======================")
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8300)