from django.db import connection
from django.http import JsonResponse


def health(request):
    """Liveness + DB readiness. Used by Docker healthchecks and uptime monitors. No auth, no data."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "database_unavailable"}, status=503)
