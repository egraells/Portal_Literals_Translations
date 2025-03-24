import requests
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from logger_manager import LoggerManager

class LLM_Einstein_Manager:
    def __init__(self, client_id, client_secret, token_url):

        self.logger = LoggerManager().get_logger()
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.access_token = None

        # More info on available models: https://developer.salesforce.com/docs/einstein/genai/guide/supported-models.html#salesforce-managed-models
        self.url = "https://api.salesforce.com/einstein/platform/v1/models/sfdc_ai__DefaultOpenAIGPT4OmniMini/generations"
        

    def get_access_token(self):
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        response = requests.post(self.token_url, data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            self.logger.error(f"Failed to fetch access token: {response.status_code} {response.text}")
            raise Exception(f"Failed to fetch access token: {response.status_code} {response.text}")

    @retry(stop=stop_after_attempt(3), 
            wait=wait_exponential(multiplier=1, min=4, max=10), 
            retry=retry_if_exception_type(requests.exceptions.RequestException))
    def call_llm(self, prompt):
        
        self.access_token = self.get_access_token()
        
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'x-sfdc-app-context': 'EinsteinGPT',
            'x-client-feature-id': 'ai-platform-models-connected-app',
            'Authorization': f'Bearer {self.access_token}'
        }
        payload = {
            "prompt": prompt
        }
        
        self.logger.info("\t->Request sent to Einstein")
        response = requests.post(self.url, headers=headers, json=payload)

        if response.status_code == 200:

            self.logger.info("\t->Response from Einstein received ")
            data = json.loads(response.text)
            result = data["generation"]["generatedText"]
            # Sometimes the response contains a JSON object header and footer
            result = result.replace("```json\n", "")  
            result = result.replace("```", "")  
            return result 

        elif response.status_code == 504:
            self.logger.error("Einstein Gateway Timeout: The server didn't respond in time. Will be retried.")
            raise requests.exceptions.RequestException("Einstein Gateway Timeout: The server didn't respond in time.")
        elif response.status_code == 401:
            self.logger.error("Einstein Unauthorized: Access token is invalid or expired.")
            raise Exception("Einstein Unauthorized: Access token is invalid or expired.")
        elif response.status_code == 403:
            self.logger.error("Einstein Forbidden: You don't have permission to access this resource.")
            raise Exception("Einstein Forbidden: You don't have permission to access this resource.")
        elif response.status_code == 404:
            self.logger.error("Einstein Not Found: The requested resource could not be found.")
            raise Exception("Einstein Not Found: The requested resource could not be found.")
        elif response.status_code == 500:
            self.logger.error("Einstein Internal Server Error: The server encountered an error.")
            raise Exception("Einstein Internal Server Error: The server encountered an error.")
        else:
            self.logger.error(f"Einstein Unexpected Error: {response.status_code} {response.text}")
            raise Exception(f"Einstein Unexpected Error: {response.status_code} {response.text}")
