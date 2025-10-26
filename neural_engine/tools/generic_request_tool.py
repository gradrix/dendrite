from .base_tool import BaseTool
import requests

class GenericRequestTool(BaseTool):
    def make_request(self, method, url, params=None, data=None, headers=None):
        """
        Makes a generic HTTP request.
        """
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
                        {
                            "name": "method",
                            "type": "string",
                            "description": "The HTTP method (e.g., GET, POST).",
                        },
                        {
                            "name": "url",
                            "type": "string",
                            "description": "The URL to make the request to.",
                        },
                        {
                            "name": "params",
                            "type": "dict",
                            "description": "URL parameters.",
                        },
                        {
                            "name": "data",
                            "type": "dict",
                            "description": "Request body.",
                        },
                        {
                            "name": "headers",
                            "type": "dict",
                            "description": "Request headers.",
                        },
                    ],
                }
            ],
        }
