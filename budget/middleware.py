from django.utils.cache import patch_cache_control


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Robots-Tag"] = "noindex, nofollow"
        patch_cache_control(response, private=True, no_store=True, max_age=0)
        return response
