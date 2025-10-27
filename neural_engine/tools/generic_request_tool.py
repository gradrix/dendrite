from .base_tool import BaseTool
import requests

class GenericRequestTool(BaseTool):
    def make_request(self, method, url, params=None, data=None, headers=None):
        try:
            response = requests.request(method, url, params=params, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def get_tool_definition(self):
        return {
            "name": "generic_request",
            "description": "A tool for making generic HTTP requests.",
            "functions": [
                {
                    "name": "make_request",
                    "description": "Make an HTTP request.",
                    "parameters": [
                        {"name": "method", "type": "string"},
                        {"name": "url", "type": "string"},
                        {"name": "params", "type": "dict"},
                        {"name": "data", "type": "dict"},
                        {"name": "headers", "type": "dict"},
                    ],
                }
            ],
        }
