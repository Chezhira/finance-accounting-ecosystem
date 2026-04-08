from db.store import OfflineStore
store = OfflineStore()
suggs = store.list_suggestions(tenant_id='acme_tanzania_limited', limit=100)
from collections import Counter
counts = Counter(s.get('status','?') for s in suggs)
print('Status counts:', dict(counts))
stats = store.stats('acme_tanzania_limited')
print('Stats endpoint:', stats)
