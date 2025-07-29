from openai import OpenAI
from typing import Dict, List, Optional, Union
import time
import json


class DeepSeekClient:
    """Generic client for DeepSeek LLM API"""
    
    def __init__(
        self, 
        api_key: str, 
        model: str = "deepseek-chat",
        max_retries: int = 2,
        retry_delay: int = 2
    ):
        """
        Initialize DeepSeek client
        
        Args:
            api_key: DeepSeek API key
            model: Model to use (default: deepseek-reasoner)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize OpenAI client with DeepSeek configuration
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def complete(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """
        Get completion from DeepSeek
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
            
        Raises:
            Exception: If API call fails after retries
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                error_msg = str(e)
                
                # Handle specific errors
                if "401" in error_msg:
                    raise Exception("Authentication failed: Check your API key")
                elif "429" in error_msg:
                    raise Exception(f"Rate limit exceeded: {error_msg}")
                elif "400" in error_msg:
                    raise Exception(f"Bad request: {error_msg}")
                
                # Retry for other errors
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"API error (attempt {attempt+1}/{self.max_retries+1}): {error_msg}")
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"API request failed after {self.max_retries+1} attempts: {error_msg}")
    
    def complete_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Union[Dict, List]:
        """
        Get JSON completion from DeepSeek
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Parsed JSON response (dict or list)
            
        Raises:
            Exception: If API call fails or response isn't valid JSON
        """
        # Add JSON instruction to system message if not present
        if messages[0]['role'] == 'system':
            messages[0]['content'] += "\n\nIMPORTANT: Return ONLY valid JSON with no additional text."
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                content = response.choices[0].message.content
                
                # Parse JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    # Try to extract JSON from the response
                    import re
                    
                    # Look for JSON array or object
                    json_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', content)
                    if json_match:
                        return json.loads(json_match.group(1))
                    else:
                        raise Exception(f"Invalid JSON in response: {str(e)}")
                
            except Exception as e:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"API error (attempt {attempt+1}/{self.max_retries+1}): {str(e)}")
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise
    
    def simple_prompt(self, prompt: str, system_message: str = None) -> str:
        """
        Convenience method for simple prompts
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            
        Returns:
            Response string
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.complete(messages)