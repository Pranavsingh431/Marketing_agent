"""Simple, fast content generator for when main generator times out."""

import json
import asyncio
import aiohttp
import logging
from typing import Dict, Any
from config import settings

logger = logging.getLogger(__name__)

class SimpleContentGenerator:
    """Ultra-fast content generator with minimal prompts."""
    
    def __init__(self):
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_simple_ad_copy(self, campaign_brief: Dict[str, Any]) -> Dict[str, Any]:
        """Generate simple ad copy with minimal prompt."""
        
        try:
            # Enhanced prompt with product details
            product_name = campaign_brief.get('product_name', 'product')
            product_description = campaign_brief.get('product_description', 'amazing product')
            special_offers = campaign_brief.get('special_offers', '')
            
            prompt = f"""Create 3 specific marketing headlines for {product_name}.

Product: {product_name}
Description: {product_description}
Special Offer: {special_offers}

REQUIREMENTS:
- Mention specific product features/benefits
- Include the special offer if provided
- NO generic phrases like "Get Product Now!"
- Be specific about what makes this product special

Format: 
1. [Specific headline about product features]
2. [Headline highlighting main benefit + offer]  
3. [Urgency headline with product name]"""
            
            payload = {
                "model": "openai/gpt-4",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.7
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(self.api_url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result['choices'][0]['message']['content']
                        
                        # Parse simple response
                        lines = content.strip().split('\n')
                        headlines = [line.split('. ', 1)[-1] for line in lines if '. ' in line]
                        
                        # Parse headlines properly
                        product_name = campaign_brief.get('product_name', 'Product')
                        special_offers = campaign_brief.get('special_offers', '')
                        
                        if not headlines:
                            # Create specific fallbacks using actual product details
                            headlines = [
                                f"New {product_name} - {special_offers}" if special_offers else f"Premium {product_name} Available",
                                f"Limited: {product_name} {special_offers.split(' ')[0] if special_offers else 'Special Price'}",
                                f"{product_name} - Professional Grade Performance"
                            ]
                        
                        return {
                            'success': True,
                            'content': {
                                'headlines': headlines[:3],
                                'descriptions': [f"Experience the {product_name} - {campaign_brief.get('product_description', 'premium quality and performance')}"],
                                'call_to_action': 'Order Now' if special_offers else 'Shop Now',
                                'generator': 'simple_fast'
                            }
                        }
                    else:
                        raise Exception(f"API Error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Simple generator failed: {e}")
            # Ultra-simple fallback
            product = campaign_brief.get('product_name', 'Product')
            # Use actual product details even in ultimate fallback
            product = campaign_brief.get('product_name', 'Product')
            description = campaign_brief.get('product_description', 'premium product')
            offers = campaign_brief.get('special_offers', '')
            
            return {
                'success': True,
                'content': {
                    'headlines': [
                        f"New {product} - {offers}" if offers else f"Premium {product}",
                        f"Limited Time: {product} {offers.split(' ')[0] if offers else 'Available'}",
                        f"Professional {product} - Order Today"
                    ],
                    'descriptions': [f"Experience the {product} - {description}"],
                    'call_to_action': 'Order Now' if offers else 'Shop Now',
                    'generator': 'fallback'
                }
            }

# Global instance
simple_generator = SimpleContentGenerator() 