from .base_tool import BaseTool
import requests

class GenericRequestTool(BaseTool):
    def get_tool_definition(self):
        return {
            "name": "generic_request",
            "description": "Makes an HTTP request to a specified URL.",
            "parameters": [
                {"name": "method", "type": "string", "required": True},
                {"name": "url", "type": "string", "required": True},
                {"name": "headers", "type": "object", "required": False},
                {"name": "body", "type": "object", "required": False}
            ]
        }

    def execute(self, **kwargs):
        method = kwargs.get("method")
        url = kwargs.get("url")
        headers = kwargs.get("headers")
        body = kwargs.get("body")

        try:
            response = requests.request(method, url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
