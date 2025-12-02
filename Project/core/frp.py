from typing import NamedTuple, Callable, Dict
from datetime import datetime
from core.domain import Event
from datetime import datetime
from typing import Callable, Dict

class EventBus:
    def __init__(self):
        self.subscribers = {}
        self.store = {}   # витрины

    def subscribe(self, name: str, handler: Callable[[Event, dict], dict]):
        self.subscribers.setdefault(name, []).append(handler)

    def publish(self, name: str, payload: Dict):
        ts = datetime.now().isoformat(timespec="seconds")
        eid = f"{name.lower()}_{ts}"

        event = Event(
            id=eid,
            ts=ts,
            name=name,
            payload=payload
        )

        for h in self.subscribers.get(name, []):
            new_store = h(event, self.store)
            if not isinstance(new_store, dict):
                raise ValueError("Handler must return a new dict")
            self.store = new_store

        return event
def handle_reading(event, store):
    sid = event.payload["sensor"]
    val = event.payload["value"]

    store.setdefault("readings", []).append({
        "sensor": sid,
        "value": val,
        "ts": event.ts
    })
    return store


def handle_alert_raised(event, store):
    aid = event.payload["id"]
    msg = event.payload["msg"]
    store.setdefault("alerts", {})[aid] = {
        "msg": msg,
        "ts": event.ts
    }
    return store


def handle_alert_cleared(event, store):
    aid = event.payload["id"]
    alerts = store.setdefault("alerts", {})
    if aid in alerts:
        del alerts[aid]
    return store


def handle_actuate(event, store):
    entry = {
        "ts": event.ts,
        "device": event.payload["device"],
        "action": event.payload["action"]
    }
    store.setdefault("commands", []).append(entry)
    return store


def handle_mode_tick(event, store):
    store["mode"] = {"mode": event.payload["mode"], "ts": event.ts}
    return store
