from api.escalation import EscalationStore
store = EscalationStore()
all_escs = store.list_all()
print(f'Total escalations: {len(all_escs)}')
for e in all_escs:
    print(f'  id={e["id"][:8]}  state={e["state"]}  tenant={e["tenant_id"]}')
pending = store.list_pending_human()
print(f'Pending human count: {len(pending)}')
for p in pending:
    print(f'  pending id={p["id"][:8]}')
