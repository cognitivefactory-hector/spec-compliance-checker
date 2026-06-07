from django.http import JsonResponse
from django.shortcuts import render


def index(request):
    """Landing page. The full flow (Upload → Requirements → Results → Report)
    is built across milestones M5–M7; for now this establishes the scaffold
    and carries the disclaimer."""
    return render(request, "index.html")


def healthz(request):
    """Liveness probe for the host (Render) and uptime checks."""
    return JsonResponse({"status": "ok"})
