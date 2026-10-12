from django.conf import settings


def centrifugo(request):
    return {"centrifugo_ws_url": settings.CENTRIFUGO_WS_URL}
