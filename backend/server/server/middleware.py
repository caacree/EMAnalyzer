from django.utils.deprecation import MiddlewareMixin
import mimetypes


class CorrectContentTypeMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith("/media/"):
            file_path = request.path
            if file_path.endswith(".dzi"):
                response["Content-Type"] = "application/xml"
            else:
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type:
                    response["Content-Type"] = mime_type
        return response
