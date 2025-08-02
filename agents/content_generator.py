"""Content Generator Agent for creating marketing copy and headlines."""

import logging
import time
from typing import Dict, List, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.callbacks import LangChainTracer
from config import settings
from utils.database import db_manager

logger = logging.getLogger(__name__)


class ContentGeneratorAgent:
    """Agent responsible for generating marketing content using AI."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            model="openai/gpt-4",  # GPT-4 works reliably for copywriting
            temperature=0.7,
            max_tokens=2000,
            timeout=60,  # Increased timeout
            request_timeout=60
        )
        
        # Initialize tracing if LangSmith is configured
        self.tracer = None
        if settings.langchain_api_key:
            self.tracer = LangChainTracer(project_name=settings.langchain_project)
    
    async def generate_ad_copy(self, campaign_brief: Dict[str, Any]) -> Dict[str, Any]:
        """Generate ad copy including headlines, descriptions, and CTAs."""
        start_time = time.time()
        
        try:
            # Extract campaign details
            product_name = campaign_brief.get('product_name', 'Product')
            target_audience = campaign_brief.get('target_audience', {})
            objective = campaign_brief.get('objective', 'conversions')
            platform = campaign_brief.get('platform', 'meta')
            budget = campaign_brief.get('budget_daily', 100)
            
            # Create platform-specific prompt
            prompt_template = self._get_platform_prompt(platform)
            
            # Format the prompt
            prompt = prompt_template.format(
                product_name=product_name,
                target_audience=self._format_audience(target_audience),
                objective=objective,
                budget=budget,
                platform=platform.upper()
            )
            
            # Generate content using LLM
            messages = [
                SystemMessage(content="You are an expert digital marketing copywriter specializing in high-converting ad copy. Create compelling, platform-optimized content that drives action."),
                HumanMessage(content=prompt)
            ]
            
            # Add tracing if available
            callbacks = [self.tracer] if self.tracer else []
            
            response = await self.llm.agenerate([messages], callbacks=callbacks)
            content = response.generations[0][0].text
            
            # Parse the generated content
            parsed_content = self._parse_generated_content(content, platform)
            
            # Calculate execution time
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log to database
            await db_manager.log_agent_execution(
                agent_name="ContentGenerator",
                campaign_id=campaign_brief.get('campaign_id'),
                action="generate_ad_copy",
                status="completed",
                input_data=campaign_brief,
                output_data=parsed_content,
                execution_time_ms=execution_time,
                langsmith_trace_id=getattr(response, 'trace_id', None)
            )
            
            logger.info(f"Generated ad copy for campaign {campaign_brief.get('campaign_id')} in {execution_time}ms")
            
            return {
                'success': True,
                'content': parsed_content,
                'execution_time_ms': execution_time
            }
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"Error generating ad copy: {str(e)}"
            logger.error(error_msg)
            
            # Log error to database
            await db_manager.log_agent_execution(
                agent_name="ContentGenerator",
                campaign_id=campaign_brief.get('campaign_id'),
                action="generate_ad_copy",
                status="failed",
                input_data=campaign_brief,
                error_message=error_msg,
                execution_time_ms=execution_time
            )
            
            return {
                'success': False,
                'error': error_msg,
                'execution_time_ms': execution_time
            }
    
    def _get_platform_prompt(self, platform: str) -> PromptTemplate:
        """Get platform-specific prompt template."""
        
        if platform.lower() == 'meta':
            return PromptTemplate(
                input_variables=["product_name", "target_audience", "objective", "budget", "platform"],
                template="""
                Create high-converting Facebook/Instagram ad copy for:
                
                Product: {product_name}
                Target Audience: {target_audience}
                Campaign Objective: {objective}
                Daily Budget: ${budget}
                Platform: {platform}
                
                Generate the following in JSON format:
                {{
                    "headlines": [
                        "Primary headline (25 chars max)",
                        "Alternative headline 1",
                        "Alternative headline 2"
                    ],
                    "primary_text": "Engaging primary text (125 chars max for feed)",
                    "description": "Compelling description (30 words max)",
                    "call_to_action": "Action-oriented CTA (Shop Now, Learn More, etc.)",
                    "hashtags": ["#relevant", "#hashtags", "#max5"]
                }}
                
                Focus on:
                - Emotional triggers and benefits
                - Social proof elements
                - Urgency when appropriate
                - Platform-native language
                - Clear value proposition
                """
            )
        
        elif platform.lower() == 'google':
            return PromptTemplate(
                input_variables=["product_name", "target_audience", "objective", "budget", "platform"],
                template="""
                Create high-converting Google Ads copy for:
                
                Product: {product_name}
                Target Audience: {target_audience}
                Campaign Objective: {objective}
                Daily Budget: ${budget}
                Platform: {platform}
                
                Generate the following in JSON format:
                {{
                    "headlines": [
                        "Headline 1 (30 chars max)",
                        "Headline 2 (30 chars max)",
                        "Headline 3 (30 chars max)"
                    ],
                    "descriptions": [
                        "Description 1 (90 chars max)",
                        "Description 2 (90 chars max)"
                    ],
                    "display_url": "displayurl.com/path",
                    "keywords": ["relevant", "keywords", "for", "targeting"],
                    "extensions": {{
                        "sitelinks": ["Feature 1", "Feature 2", "Feature 3"],
                        "callouts": ["Free Shipping", "24/7 Support", "Money Back Guarantee"]
                    }}
                }}
                
                Focus on:
                - Search intent alignment
                - Keyword integration
                - Competitive advantages
                - Clear value proposition
                - Action-oriented language
                """
            )
        
        else:
            # Generic template for both platforms
            return PromptTemplate(
                input_variables=["product_name", "target_audience", "objective", "budget", "platform"],
                template="""
                Create marketing ad copy for:
                
                Product: {product_name}
                Target Audience: {target_audience}
                Campaign Objective: {objective}
                Daily Budget: ${budget}
                Platform: {platform}
                
                Generate compelling headlines, descriptions, and call-to-action buttons optimized for the specified platform.
                Return the content in a structured JSON format appropriate for {platform}.
                """
            )
    
    def _format_audience(self, target_audience: Dict[str, Any]) -> str:
        """Format target audience dictionary into readable string."""
        if not target_audience:
            return "General audience"
        
        parts = []
        if target_audience.get('age_range'):
            parts.append(f"Age: {target_audience['age_range']}")
        if target_audience.get('interests'):
            parts.append(f"Interests: {', '.join(target_audience['interests'][:3])}")
        if target_audience.get('location'):
            parts.append(f"Location: {target_audience['location']}")
        if target_audience.get('behavior'):
            parts.append(f"Behavior: {target_audience['behavior']}")
        
        return "; ".join(parts) if parts else "General audience"
    
    def _parse_generated_content(self, content: str, platform: str) -> Dict[str, Any]:
        """Parse and validate generated content."""
        try:
            import json
            
            # Try to extract JSON from the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                # Validate required fields based on platform
                if platform.lower() == 'meta':
                    required_fields = ['headlines', 'primary_text', 'description', 'call_to_action']
                elif platform.lower() == 'google':
                    required_fields = ['headlines', 'descriptions']
                else:
                    required_fields = ['headlines']
                
                for field in required_fields:
                    if field not in parsed:
                        logger.warning(f"Missing required field: {field}")
                
                return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON content: {e}")
        
        # Fallback: return basic structure with raw content
        return {
            'headlines': ['Generated Headline'],
            'primary_text': content[:125] if len(content) > 125 else content,
            'description': content[:100] if len(content) > 100 else content,
            'call_to_action': 'Learn More',
            'raw_content': content
        }
    
    async def optimize_content(self, current_content: Dict[str, Any], 
                             performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize existing content based on performance data."""
        start_time = time.time()
        
        try:
            ctr = performance_data.get('ctr', 0)
            cpc = performance_data.get('cpc', 0)
            conversions = performance_data.get('conversions', 0)
            
            # Create optimization prompt
            optimization_prompt = f"""
            Current ad content performance:
            - CTR: {ctr:.3f}
            - CPC: ${cpc:.2f}
            - Conversions: {conversions}
            
            Current content:
            {current_content}
            
            Based on the performance data, optimize this content to improve:
            - Click-through rate (target: >{settings.ctr_threshold})
            - Cost per click (target: <${settings.cpc_threshold})
            - Conversion rate
            
            Provide 3 alternative versions with explanations for changes made.
            Return in JSON format with the same structure as the original content.
            """
            
            messages = [
                SystemMessage(content="You are an expert at optimizing ad content based on performance data. Focus on data-driven improvements."),
                HumanMessage(content=optimization_prompt)
            ]
            
            callbacks = [self.tracer] if self.tracer else []
            response = await self.llm.agenerate([messages], callbacks=callbacks)
            
            optimized_content = self._parse_generated_content(response.generations[0][0].text, 'optimization')
            
            execution_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"Optimized content based on performance data in {execution_time}ms")
            
            return {
                'success': True,
                'optimized_content': optimized_content,
                'execution_time_ms': execution_time
            }
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"Error optimizing content: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'execution_time_ms': execution_time
            }


# Global content generator instance
content_generator = ContentGeneratorAgent() 