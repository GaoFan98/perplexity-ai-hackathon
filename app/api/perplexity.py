import httpx
import json
import logging
from typing import List, Dict, Any, Optional, Union
import base64
from io import BytesIO
from PIL import Image
import re

logger = logging.getLogger(__name__)

class PerplexityAPI:
    """Class to interact with Perplexity API."""
    
    def __init__(self, api_key: str):
        """Initialize with API key."""
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai"
        self.default_model = "sonar-pro"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def ask_question(
        self, 
        query: str, 
        model: str = None, 
        conversation_history: List[Dict[str, str]] = None,
        show_thinking: bool = False,
        temperature: float = 0.2,
        system_prompt: str = "You are a helpful AI assistant. Provide accurate, detailed responses to questions. If you don't know the answer, say so instead of making things up.",
        image_data: Optional[bytes] = None,
        search_domain_filter: Optional[List[str]] = None,
        search_recency_filter: Optional[str] = None,
        search_context_size: Optional[str] = "medium"
    ) -> Dict[str, Any]:
        """
        Ask a question to Perplexity API.
        
        Args:
            query: The question to ask
            model: The model to use (defaults to sonar-pro)
            conversation_history: Previous conversation history
            show_thinking: Whether to show thinking process (if available)
            temperature: Model temperature (0.0 to 2.0)
            system_prompt: System prompt to guide the model
            image_data: Optional image data to include with the query
            search_domain_filter: Optional list of domains to filter search results
            search_recency_filter: Optional filter for recency ('day', 'week', 'month', etc)
            search_context_size: Optional size of search context ('low', 'medium', 'high')
            
        Returns:
            Response from Perplexity API
        """
        model = model or self.default_model
        
        # For reasoning models, switch to reasoning model if thinking is enabled
        if show_thinking and not "reasoning" in model:
            # If not already a reasoning model, switch to an appropriate one
            if model == "sonar-pro":
                model = "sonar-reasoning-pro"
            elif model == "sonar":
                model = "sonar-reasoning"
            logger.info(f"Thinking mode enabled: switched model from {model} to reasoning variant")
        
        # Prepare messages
        messages = []
        
        # Add system prompt
        # For reasoning models, add instructions to use <think> tags when thinking mode is enabled
        if show_thinking and "reasoning" in model:
            enhanced_prompt = (
                f"{system_prompt}\n\n"
                "IMPORTANT: For this question, I want to see your step-by-step reasoning process. "
                "Please provide your thinking and reasoning within <think></think> tags, "
                "and then provide your final answer after the closing tag. "
                "For example: <think>Here's my reasoning...</think> Here's my final answer."
            )
            messages.append({
                "role": "system",
                "content": enhanced_prompt
            })
        else:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add conversation history if provided
        if conversation_history:
            # Skip the first message if it's a system message to avoid duplication
            history_to_add = conversation_history
            if (conversation_history and len(conversation_history) > 0 and 
                conversation_history[0].get("role") == "system"):
                history_to_add = conversation_history[1:]
                
            messages.extend(history_to_add)
        
        # Prepare user message with text and optional image
        if image_data:
            # Convert image to base64
            base64_image = self._encode_image(image_data)
            
            # Create content array with text and image
            content = [
                {"type": "text", "text": query},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
            
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            # Simple text-only message
            messages.append({
                "role": "user",
                "content": query
            })
        
        # Prepare payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        # Configure web search options
        web_search_options = {}
        
        # Add search context size if provided
        if search_context_size and search_context_size in ["low", "medium", "high"]:
            web_search_options["search_context_size"] = search_context_size
        
        # Add web_search_options to payload if not empty
        if web_search_options:
            payload["web_search_options"] = web_search_options
        
        # Add optional parameters if provided
        if search_domain_filter:
            payload["search_domain_filter"] = search_domain_filter
            
        if search_recency_filter:
            payload["search_recency_filter"] = search_recency_filter
            
        url = f"{self.base_url}/chat/completions"
        
        try:
            async with httpx.AsyncClient() as client:
                # Log the request payload for debugging (without sensitive info)
                debug_payload = payload.copy()
                if "messages" in debug_payload:
                    # Truncate message content for logging
                    debug_payload["messages"] = f"{len(debug_payload['messages'])} messages"
                logger.debug(f"Sending request to Perplexity API: {model} - {debug_payload}")
                
                response = await client.post(
                    url, 
                    headers=self.headers, 
                    json=payload,
                    timeout=90.0  # Longer timeout for deep research
                )
                
                if response.status_code != 200:
                    error_message = response.text
                    try:
                        error_json = response.json()
                        if "error" in error_json and "message" in error_json["error"]:
                            error_message = error_json["error"]["message"]
                    except:
                        # If we can't parse the JSON, use the raw text
                        pass
                        
                    logger.error(f"Error from Perplexity API: {response.status_code} - {error_message}")
                    
                    # Log message structure for debugging
                    if "After the (optional) system message(s), user and assistant roles should be alternating" in response.text:
                        roles = [m.get("role", "unknown") for m in messages]
                        logger.error(f"Message role sequence: {roles}")
                    
                    return {
                        "success": False,
                        "error": f"API Error: {response.status_code} - {error_message}"
                    }
                
                data = response.json()
                
                # Extract response content
                content = data["choices"][0]["message"]["content"]
                
                # Check if there are search results with links
                search_results = None
                if "search_results" in data.get("choices", [{}])[0].get("message", {}).get("metadata", {}):
                    search_results = data["choices"][0]["message"]["metadata"]["search_results"]
                
                # Clean up any assistant tags at the beginning
                content = re.sub(r'^(&amp;lt;｜Assistant｜&amp;gt;|<｜Assistant｜>)', '', content).strip()
                
                # For reasoning models, extract thinking and final answer if show_thinking is enabled
                if show_thinking:
                    # Try to extract thinking content using tags
                    if "<think>" in content and "</think>" in content:
                        # Extract content between <think> tags
                        think_start = content.find("<think>") + len("<think>")
                        think_end = content.find("</think>")
                        thinking = content[think_start:think_end].strip()
                        
                        # Extract content after </think>
                        answer = content[think_end + len("</think>"):].strip()
                        
                        return {
                            "success": True,
                            "thinking": thinking,
                            "answer": answer,
                            "model": model,
                            "search_results": search_results,
                            "full_response": data
                        }
                    # If no explicit tags but model is a reasoning model, try other patterns
                    elif "reasoning" in model:
                        # Check for "📝 Answer:" marker which often separates thinking from answer
                        if "📝 Answer:" in content:
                            parts = content.split("📝 Answer:", 1)
                            if len(parts) == 2:
                                thinking = parts[0].strip()
                                answer = parts[1].strip()
                                
                                # Make sure we don't have thinking content after the answer
                                if "Here's my reasoning process:" in answer:
                                    answer = answer.split("Here's my reasoning process:", 1)[0].strip()
                                    
                                return {
                                    "success": True,
                                    "thinking": thinking,
                                    "answer": answer,
                                    "model": model,
                                    "search_results": search_results,
                                    "full_response": data
                                }
                                
                        # Look for other patterns like "Thinking:" or "Reasoning:"
                        patterns = [
                            (r"(?i)Thinking:\s*(.+?)(?=\n\n📝 Answer:|$)", r"(?i)📝 Answer:\s*(.+)"),
                            (r"(?i)Here's my reasoning process:\s*(.+?)(?=\n\n📝 Answer:|$)", r"(?i)📝 Answer:\s*(.+)"),
                            (r"(?i)Reasoning:\s*(.+?)(?=\n\nAnswer:|$)", r"(?i)Answer:\s*(.+)"),
                            (r"(?i)Step by step:\s*(.+?)(?=\n\nResponse:|$)", r"(?i)Response:\s*(.+)"),
                            (r"(?i)Analysis:\s*(.+?)(?=\n\nConclusion:|$)", r"(?i)Conclusion:\s*(.+)")
                        ]
                        
                        for thinking_pattern, answer_pattern in patterns:
                            thinking_match = re.search(thinking_pattern, content, re.DOTALL)
                            answer_match = re.search(answer_pattern, content, re.DOTALL)
                            
                            if thinking_match and answer_match:
                                thinking = thinking_match.group(1).strip()
                                answer = answer_match.group(1).strip()
                                
                                # Make sure there's no continuation of thinking after answer has started
                                if "Here's my reasoning process:" in answer:
                                    answer = answer.split("Here's my reasoning process:", 1)[0].strip()
                                
                                return {
                                    "success": True,
                                    "thinking": thinking,
                                    "answer": answer,
                                    "model": model,
                                    "search_results": search_results,
                                    "full_response": data
                                }
                        
                        # If no patterns match, try to split at clear answer section headings
                        content_splits = re.split(r'\n\n---\n\n|\n---\n|\n\n#|📝 Answer:', content)
                        if len(content_splits) > 1:
                            # Use everything before first split as thinking
                            thinking = content_splits[0].strip()
                            # Use everything after as answer
                            answer = "\n\n".join(content_splits[1:]).strip()
                            
                            return {
                                "success": True,
                                "thinking": thinking,
                                "answer": answer,
                                "model": model,
                                "search_results": search_results,
                                "full_response": data
                            }
                            
                        # Last resort: look for numbered list items followed by answer
                        match = re.search(r'(\d+)\.\s+(.*?)(?=\n\n📝\s+Answer:|\n📝\s+Answer:)', content, re.DOTALL)
                        if match:
                            # Find where the numbered thinking ends and the answer begins
                            answer_start = content.find("📝 Answer:")
                            if answer_start > 0:
                                thinking = content[:answer_start].strip()
                                answer = content[answer_start + len("📝 Answer:"):].strip()
                                
                                return {
                                    "success": True,
                                    "thinking": thinking,
                                    "answer": answer, 
                                    "model": model,
                                    "search_results": search_results,
                                    "full_response": data
                                }
                                
                        # If still no match, split the content roughly in half as a fallback
                        content_parts = content.split("\n\n")
                        if len(content_parts) > 2:
                            # Use first half as thinking, second half as answer
                            midpoint = len(content_parts) // 2
                            thinking = "\n\n".join(content_parts[:midpoint]).strip()
                            answer = "\n\n".join(content_parts[midpoint:]).strip()
                            
                            return {
                                "success": True,
                                "thinking": thinking,
                                "answer": answer,
                                "model": model,
                                "search_results": search_results,
                                "full_response": data
                            }
                
                # If we didn't return thinking/answer above, return the full content as answer
                return {
                    "success": True,
                    "answer": content,
                    "model": model,
                    "search_results": search_results,
                    "full_response": data
                }
                
        except httpx.RequestError as e:
            logger.error(f"Request error when calling Perplexity API: {str(e)}")
            return {
                "success": False,
                "error": f"Request error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error when calling Perplexity API: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    async def generate_image(self, prompt: str) -> Dict[str, Any]:
        """
        Generate an image based on a text prompt.
        
        Note: Perplexity doesn't have a native image generation API, so this is a mock.
        We can potentially integrate with another image generation API in the future.
        
        Args:
            prompt: The image description
            
        Returns:
            A mock response indicating we need to use a different service
        """
        logger.info(f"Image generation requested for prompt: {prompt}")
        
        # For now, we'll return a mock response
        # In a real implementation, we would integrate with a service like DALL-E or Stable Diffusion
        return {
            "success": False,
            "error": "Image generation is not supported by Perplexity API. Please integrate with a dedicated image generation service."
        }
    
    def _encode_image(self, image_data: bytes) -> str:
        """
        Encode image data to base64 string. Also compress the image if it's too large.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Base64 encoded string
        """
        try:
            # Open image with Pillow
            img = Image.open(BytesIO(image_data))
            
            # Check file size
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format=img.format or 'JPEG')
            file_size = img_byte_arr.tell()
            
            # If image is too large, compress it
            if file_size > 4 * 1024 * 1024:  # 4MB
                # Calculate new size to maintain aspect ratio
                width, height = img.size
                ratio = min(1000 / width, 1000 / height)
                new_size = (int(width * ratio), int(height * ratio))
                
                # Resize image
                img = img.resize(new_size, Image.LANCZOS)
                
                # Save as JPEG with compression
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=85)
                img_byte_arr.seek(0)
                image_data = img_byte_arr.read()
            
            # Encode to base64
            base64_str = base64.b64encode(image_data).decode('utf-8')
            return base64_str
            
        except Exception as e:
            logger.error(f"Error encoding image: {str(e)}")
            raise ValueError(f"Error processing image: {str(e)}")
            
    async def get_available_models(self) -> List[Dict[str, str]]:
        """
        Get a list of available models with descriptions.
        
        Returns:
            List of models with descriptions
        """
        return [
            {
                "id": "sonar-pro",
                "name": "Sonar Pro",
                "description": "Advanced search offering with grounding, supporting complex queries and follow-ups."
            },
            {
                "id": "sonar",
                "name": "Sonar",
                "description": "Lightweight, cost-effective search model with grounding."
            },
            {
                "id": "sonar-reasoning-pro",
                "name": "Sonar Reasoning Pro",
                "description": "Premier reasoning offering powered by DeepSeek R1 with Chain of Thought (CoT)."
            },
            {
                "id": "sonar-reasoning",
                "name": "Sonar Reasoning",
                "description": "Fast, real-time reasoning model designed for quick problem-solving with search."
            },
            {
                "id": "sonar-deep-research",
                "name": "Sonar Deep Research",
                "description": "Expert-level research model conducting exhaustive searches and generating comprehensive reports."
            },
            {
                "id": "r1-1776",
                "name": "R1-1776",
                "description": "A version of DeepSeek R1 post-trained for uncensored, unbiased, and factual information."
            }
        ] 