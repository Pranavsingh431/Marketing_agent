"""Performance Tracker Agent for monitoring campaign metrics and KPIs."""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adsinsights import AdsInsights
from google.ads.googleads.client import GoogleAdsClient
from config import settings
from utils.database import db_manager

logger = logging.getLogger(__name__)


class PerformanceTrackerAgent:
    """Agent responsible for tracking and monitoring campaign performance metrics."""
    
    def __init__(self):
        self.meta_api = None
        self.google_ads_client = None
        self._initialize_apis()
    
    def _initialize_apis(self):
        """Initialize Meta and Google Ads APIs."""
        try:
            # Initialize Meta API
            FacebookAdsApi.init(
                app_id=settings.meta_app_id,
                app_secret=settings.meta_app_secret,
                access_token=settings.meta_access_token
            )
            self.meta_api = FacebookAdsApi.get_default_api()
            logger.info("Meta API initialized for performance tracking")
        except Exception as e:
            logger.error(f"Failed to initialize Meta API: {e}")
        
        try:
            # Initialize Google Ads API
            credentials = {
                "developer_token": settings.google_ads_developer_token,
                "client_id": settings.google_ads_client_id,
                "client_secret": settings.google_ads_client_secret,
                "refresh_token": settings.google_ads_refresh_token,
                "use_proto_plus": True
            }
            self.google_ads_client = GoogleAdsClient.load_from_dict(credentials)
            logger.info("Google Ads API initialized for performance tracking")
        except Exception as e:
            logger.error(f"Failed to initialize Google Ads API: {e}")
    
    async def track_all_campaigns(self) -> Dict[str, Any]:
        """Track performance for all active campaigns."""
        start_time = time.time()
        
        try:
            # Get all active campaigns
            active_campaigns = await db_manager.get_active_campaigns()
            
            if not active_campaigns:
                logger.info("No active campaigns to track")
                return {'success': True, 'campaigns_tracked': 0}
            
            results = []
            
            for campaign in active_campaigns:
                campaign_id = campaign['id']
                platform = campaign['platform']
                
                try:
                    # Track based on platform
                    if platform == 'meta':
                        performance_data = await self._track_meta_campaign(campaign)
                    elif platform == 'google':
                        performance_data = await self._track_google_campaign(campaign)
                    elif platform == 'both':
                        # Track both platforms
                        meta_data = await self._track_meta_campaign(campaign)
                        google_data = await self._track_google_campaign(campaign)
                        performance_data = self._combine_platform_data(meta_data, google_data)
                    else:
                        logger.warning(f"Unknown platform for campaign {campaign_id}: {platform}")
                        continue
                    
                    if performance_data:
                        # Log performance to database
                        await db_manager.log_performance(performance_data)
                        results.append(performance_data)
                        
                        # Check for optimization triggers
                        await self._check_optimization_triggers(campaign, performance_data)
                        
                        logger.info(f"Tracked performance for campaign {campaign_id}")
                    
                except Exception as e:
                    logger.error(f"Error tracking campaign {campaign_id}: {e}")
                    continue
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log agent execution
            await db_manager.log_agent_execution(
                agent_name="PerformanceTracker",
                campaign_id=None,  # Multiple campaigns
                action="track_all_campaigns",
                status="completed",
                input_data={'campaigns_count': len(active_campaigns)},
                output_data={'results_count': len(results)},
                execution_time_ms=execution_time
            )
            
            logger.info(f"Tracked {len(results)} campaigns in {execution_time}ms")
            
            return {
                'success': True,
                'campaigns_tracked': len(results),
                'results': results,
                'execution_time_ms': execution_time
            }
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"Error tracking campaigns: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'execution_time_ms': execution_time
            }
    
    async def _track_meta_campaign(self, campaign: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Track Meta campaign performance."""
        
        if not self.meta_api or not campaign.get('meta_campaign_id'):
            return None
        
        try:
            meta_campaign_id = campaign['meta_campaign_id']
            
            # Define the fields we want to retrieve
            fields = [
                'impressions',
                'clicks',
                'ctr',
                'cpc',
                'spend',
                'conversions',
                'conversion_values',
                'cost_per_conversion'
            ]
            
            # Define parameters for the insights request
            params = {
                'time_range': {
                    'since': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d'),
                    'until': datetime.now().strftime('%Y-%m-%d')
                },
                'level': 'campaign'
            }
            
            # Get insights
            meta_campaign = Campaign(meta_campaign_id)
            insights = meta_campaign.get_insights(fields=fields, params=params)
            
            if insights:
                insight = insights[0]
                
                # Calculate ROAS
                spend = float(insight.get('spend', 0))
                conversion_value = float(insight.get('conversion_values', 0))
                roas = (conversion_value / spend) if spend > 0 else 0
                
                performance_data = {
                    'campaign_id': campaign['id'],
                    'platform': 'meta',
                    'impressions': int(insight.get('impressions', 0)),
                    'clicks': int(insight.get('clicks', 0)),
                    'ctr': float(insight.get('ctr', 0)) / 100,  # Convert percentage to decimal
                    'cpc': float(insight.get('cpc', 0)),
                    'spend': spend,
                    'conversions': int(insight.get('conversions', 0)),
                    'revenue': conversion_value,
                    'roas': roas
                }
                
                return performance_data
            
        except Exception as e:
            logger.error(f"Error tracking Meta campaign {campaign.get('meta_campaign_id')}: {e}")
        
        return None
    
    async def _track_google_campaign(self, campaign: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Track Google Ads campaign performance."""
        
        if not self.google_ads_client or not campaign.get('google_campaign_id'):
            return None
        
        try:
            google_campaign_id = campaign['google_campaign_id']
            customer_id = settings.google_ads_customer_id
            
            # Build the query for campaign performance
            query = f"""
            SELECT
                campaign.id,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE campaign.id = {google_campaign_id}
            AND segments.date >= '{(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d')}'
            AND segments.date <= '{datetime.now().strftime('%Y-%m-%d')}'
            """
            
            ga_service = self.google_ads_client.get_service("GoogleAdsService")
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            # Process results
            total_impressions = 0
            total_clicks = 0
            total_cost_micros = 0
            total_conversions = 0
            total_conversion_value = 0
            
            for batch in response:
                for row in batch.results:
                    total_impressions += row.metrics.impressions
                    total_clicks += row.metrics.clicks
                    total_cost_micros += row.metrics.cost_micros
                    total_conversions += row.metrics.conversions
                    total_conversion_value += row.metrics.conversions_value
            
            if total_impressions > 0:
                # Calculate metrics
                ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0
                spend = total_cost_micros / 1000000  # Convert from micros to dollars
                cpc = (spend / total_clicks) if total_clicks > 0 else 0
                roas = (total_conversion_value / spend) if spend > 0 else 0
                
                performance_data = {
                    'campaign_id': campaign['id'],
                    'platform': 'google',
                    'impressions': total_impressions,
                    'clicks': total_clicks,
                    'ctr': ctr,
                    'cpc': cpc,
                    'spend': spend,
                    'conversions': int(total_conversions),
                    'revenue': total_conversion_value,
                    'roas': roas
                }
                
                return performance_data
            
        except Exception as e:
            logger.error(f"Error tracking Google campaign {campaign.get('google_campaign_id')}: {e}")
        
        return None
    
    def _combine_platform_data(self, meta_data: Optional[Dict[str, Any]], 
                              google_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Combine performance data from both platforms."""
        
        if not meta_data and not google_data:
            return None
        
        if not meta_data:
            return google_data
        
        if not google_data:
            return meta_data
        
        # Combine the metrics
        combined_data = {
            'campaign_id': meta_data['campaign_id'],
            'platform': 'both',
            'impressions': meta_data['impressions'] + google_data['impressions'],
            'clicks': meta_data['clicks'] + google_data['clicks'],
            'spend': meta_data['spend'] + google_data['spend'],
            'conversions': meta_data['conversions'] + google_data['conversions'],
            'revenue': meta_data['revenue'] + google_data['revenue']
        }
        
        # Calculate combined metrics
        combined_data['ctr'] = (combined_data['clicks'] / combined_data['impressions']) if combined_data['impressions'] > 0 else 0
        combined_data['cpc'] = (combined_data['spend'] / combined_data['clicks']) if combined_data['clicks'] > 0 else 0
        combined_data['roas'] = (combined_data['revenue'] / combined_data['spend']) if combined_data['spend'] > 0 else 0
        
        return combined_data
    
    async def _check_optimization_triggers(self, campaign: Dict[str, Any], 
                                         performance_data: Dict[str, Any]):
        """Check if performance triggers optimization needs."""
        
        campaign_id = campaign['id']
        ctr = performance_data.get('ctr', 0)
        cpc = performance_data.get('cpc', 0)
        roas = performance_data.get('roas', 0)
        spend = performance_data.get('spend', 0)
        
        triggers = []
        
        # Check CTR threshold
        if ctr < settings.ctr_threshold:
            triggers.append(f"Low CTR: {ctr:.3f} < {settings.ctr_threshold}")
        
        # Check CPC threshold
        if cpc > settings.cpc_threshold:
            triggers.append(f"High CPC: ${cpc:.2f} > ${settings.cpc_threshold}")
        
        # Check ROAS threshold
        if roas < settings.roas_threshold:
            triggers.append(f"Low ROAS: {roas:.2f} < {settings.roas_threshold}")
        
        # Check daily budget limit
        if spend > settings.daily_budget_limit:
            triggers.append(f"Over budget: ${spend:.2f} > ${settings.daily_budget_limit}")
        
        if triggers:
            # Log optimization trigger
            trigger_reason = "; ".join(triggers)
            
            logger.warning(f"Optimization triggers for campaign {campaign_id}: {trigger_reason}")
            
            # Could trigger optimization agent here
            # await optimization_agent.optimize_campaign(campaign_id, performance_data, trigger_reason)
    
    async def get_campaign_performance_summary(self, campaign_id: str, 
                                              hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for a specific campaign."""
        
        try:
            performance_logs = await db_manager.get_campaign_performance(campaign_id, hours)
            
            if not performance_logs:
                return {
                    'success': False,
                    'error': 'No performance data found'
                }
            
            # Calculate summary metrics
            total_impressions = sum(log.get('impressions', 0) for log in performance_logs)
            total_clicks = sum(log.get('clicks', 0) for log in performance_logs)
            total_spend = sum(log.get('spend', 0) for log in performance_logs)
            total_conversions = sum(log.get('conversions', 0) for log in performance_logs)
            total_revenue = sum(log.get('revenue', 0) for log in performance_logs)
            
            # Calculate averages
            avg_ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0
            avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            avg_roas = (total_revenue / total_spend) if total_spend > 0 else 0
            
            # Determine status based on thresholds
            status = 'green'
            if (avg_ctr < settings.ctr_threshold or 
                avg_cpc > settings.cpc_threshold or 
                avg_roas < settings.roas_threshold):
                status = 'red'
            elif (avg_ctr < settings.ctr_threshold * 1.5 or 
                  avg_cpc > settings.cpc_threshold * 0.8):
                status = 'yellow'
            
            summary = {
                'success': True,
                'campaign_id': campaign_id,
                'period_hours': hours,
                'data_points': len(performance_logs),
                'metrics': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_spend': total_spend,
                    'total_conversions': total_conversions,
                    'total_revenue': total_revenue,
                    'avg_ctr': avg_ctr,
                    'avg_cpc': avg_cpc,
                    'avg_roas': avg_roas
                },
                'status': status,
                'latest_update': performance_logs[0]['timestamp'] if performance_logs else None
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting performance summary for campaign {campaign_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def start_continuous_tracking(self, interval_minutes: int = 60):
        """Start continuous performance tracking."""
        logger.info(f"Starting continuous performance tracking (every {interval_minutes} minutes)")
        
        while True:
            try:
                await self.track_all_campaigns()
                await asyncio.sleep(interval_minutes * 60)  # Convert to seconds
            except Exception as e:
                logger.error(f"Error in continuous tracking: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying


# Global performance tracker instance
performance_tracker = PerformanceTrackerAgent() 