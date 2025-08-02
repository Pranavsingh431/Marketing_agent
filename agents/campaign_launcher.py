"""Campaign Launcher Agent for creating and launching ads on Meta and Google platforms."""

import logging
import time
import warnings
from typing import Dict, List, Any, Optional

# Suppress urllib3 SSL warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+")
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.campaign import Campaign
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from config import settings
from utils.database import db_manager

logger = logging.getLogger(__name__)


class CampaignLauncherAgent:
    """Agent responsible for launching campaigns on Meta and Google platforms."""
    
    def __init__(self):
        self._setup_meta_api()
        self._setup_google_ads_api()
    
    def _setup_meta_api(self):
        """Initialize Meta/Facebook Ads API."""
        try:
            # Check if we have proper Meta credentials
            if (not settings.meta_app_secret or settings.meta_app_secret == "placeholder_app_secret" or
                not settings.meta_ad_account_id or settings.meta_ad_account_id == "placeholder_ad_account_id"):
                logger.info("Meta API credentials incomplete, using simulation mode")
                self.meta_api = None
                self.meta_simulation_mode = True
                return
            
            FacebookAdsApi.init(
                app_id=settings.meta_app_id,
                app_secret=settings.meta_app_secret,
                access_token=settings.meta_access_token
            )
            self.meta_api = FacebookAdsApi.get_default_api()
            self.meta_simulation_mode = False
            logger.info("Meta Ads API initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Meta API: {e}")
            self.meta_api = None
            self.meta_simulation_mode = True
    
    def _setup_google_ads_api(self):
        """Initialize Google Ads API."""
        try:
            # Check if we have proper Google Ads credentials
            if (not settings.google_ads_developer_token or settings.google_ads_developer_token == "placeholder_developer_token" or
                not settings.google_ads_refresh_token or settings.google_ads_refresh_token == "placeholder_refresh_token" or
                not settings.google_ads_customer_id or settings.google_ads_customer_id == "placeholder_customer_id"):
                logger.info("Google Ads API credentials incomplete, using simulation mode")
                self.google_ads_client = None
                self.google_simulation_mode = True
                return
            
            # Create credentials dict for Google Ads
            credentials = {
                "developer_token": settings.google_ads_developer_token,
                "client_id": settings.google_ads_client_id,
                "client_secret": settings.google_ads_client_secret,
                "refresh_token": settings.google_ads_refresh_token,
                "use_proto_plus": True
            }
            
            # Try to initialize and validate credentials
            self.google_ads_client = GoogleAdsClient.load_from_dict(credentials)
            
            # Test the client with a simple call to validate credentials
            try:
                customer_service = self.google_ads_client.get_service("CustomerService")
                # This will fail if credentials are invalid
                customer_service.list_accessible_customers()
                self.google_simulation_mode = False
                logger.info("Google Ads API initialized and validated successfully")
            except Exception as validation_error:
                logger.warning(f"Google Ads credentials validation failed: {validation_error}")
                logger.info("Switching to Google Ads simulation mode")
                self.google_ads_client = None
                self.google_simulation_mode = True
                
        except Exception as e:
            # Handle specific OAuth errors gracefully
            if "invalid_grant" in str(e).lower() or "bad request" in str(e).lower():
                logger.info("Google Ads API credentials are invalid (invalid_grant), using simulation mode")
            else:
                logger.error(f"Failed to initialize Google Ads API: {e}")
            self.google_ads_client = None
            self.google_simulation_mode = True
    
    async def launch_campaign(self, campaign_data: Dict[str, Any], 
                             creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """Launch campaign on specified platform(s)."""
        start_time = time.time()
        campaign_id = campaign_data.get('campaign_id')
        platform = campaign_data.get('platform', 'meta').lower()
        
        results = {}
        
        try:
            if platform == 'meta' or platform == 'both':
                meta_result = await self._launch_meta_campaign(campaign_data, creative_data)
                results['meta'] = meta_result
                
                if meta_result['success']:
                    # Update campaign with Meta campaign ID
                    campaign_data['meta_campaign_id'] = meta_result['campaign_id']
            
            if platform == 'google' or platform == 'both':
                google_result = await self._launch_google_campaign(campaign_data, creative_data)
                results['google'] = google_result
                
                if google_result['success']:
                    # Update campaign with Google campaign ID
                    campaign_data['google_campaign_id'] = google_result['campaign_id']
            
            # Check overall success
            overall_success = any(result.get('success', False) for result in results.values())
            
            execution_time = int((time.time() - start_time) * 1000)
            
            if overall_success:
                # Update campaign status to active
                await db_manager.update_campaign_status(campaign_id, 'active')
                
                # Log successful launch
                await db_manager.log_agent_execution(
                    agent_name="CampaignLauncher",
                    campaign_id=campaign_id,
                    action="launch_campaign",
                    status="completed",
                    input_data={'campaign_data': campaign_data, 'creative_data': creative_data},
                    output_data=results,
                    execution_time_ms=execution_time
                )
                
                logger.info(f"Successfully launched campaign {campaign_id} on {platform} in {execution_time}ms")
                
                return {
                    'success': True,
                    'results': results,
                    'execution_time_ms': execution_time
                }
            else:
                raise Exception("Failed to launch on any platform")
                
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"Error launching campaign: {str(e)}"
            logger.error(error_msg)
            
            # Log error
            await db_manager.log_agent_execution(
                agent_name="CampaignLauncher",
                campaign_id=campaign_id,
                action="launch_campaign",
                status="failed",
                input_data={'campaign_data': campaign_data, 'creative_data': creative_data},
                error_message=error_msg,
                execution_time_ms=execution_time
            )
            
            return {
                'success': False,
                'error': error_msg,
                'results': results,
                'execution_time_ms': execution_time
            }
    
    async def _launch_meta_campaign(self, campaign_data: Dict[str, Any], 
                                   creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """Launch campaign on Meta platform."""
        
        # Use simulation mode if API not properly configured
        if not self.meta_api or getattr(self, 'meta_simulation_mode', True):
            return await self._simulate_meta_launch(campaign_data, creative_data)
        
        try:
            ad_account_id = settings.meta_ad_account_id
            
            # Step 1: Create Campaign
            campaign_params = {
                'name': campaign_data['name'],
                'objective': self._map_objective_to_meta(campaign_data.get('objective', 'CONVERSIONS')),
                'status': 'PAUSED',  # Start paused for safety
                'special_ad_categories': []
            }
            
            campaign = Campaign(parent_id=f"act_{ad_account_id}")
            campaign.update(campaign_params)
            campaign.remote_create()
            
            meta_campaign_id = campaign['id']
            logger.info(f"Created Meta campaign: {meta_campaign_id}")
            
            # Step 2: Create Ad Set
            adset_params = {
                'name': f"{campaign_data['name']} - AdSet",
                'campaign_id': meta_campaign_id,
                'daily_budget': int(campaign_data.get('budget_daily', 100) * 100),  # Convert to cents
                'billing_event': 'IMPRESSIONS',
                'optimization_goal': 'LINK_CLICKS',
                'bid_amount': 200,  # Starting bid in cents
                'targeting': self._build_meta_targeting(campaign_data.get('target_audience', {})),
                'status': 'PAUSED',
                'start_time': campaign_data.get('start_date'),
                'end_time': campaign_data.get('end_date')
            }
            
            adset = AdSet(parent_id=f"act_{ad_account_id}")
            adset.update(adset_params)
            adset.remote_create()
            
            adset_id = adset['id']
            logger.info(f"Created Meta adset: {adset_id}")
            
            # Step 3: Create Ad Creative
            creative_params = {
                'name': f"{campaign_data['name']} - Creative",
                'object_story_spec': {
                    'page_id': settings.meta_app_id,  # You might need a separate page ID
                    'link_data': {
                        'link': campaign_data.get('landing_url', 'https://example.com'),
                        'message': creative_data.get('primary_text', ''),
                        'name': creative_data.get('headlines', [''])[0],
                        'description': creative_data.get('description', ''),
                        'call_to_action': {
                            'type': self._map_cta_to_meta(creative_data.get('call_to_action', 'LEARN_MORE'))
                        }
                    }
                }
            }
            
            if creative_data.get('image_url'):
                creative_params['object_story_spec']['link_data']['picture'] = creative_data['image_url']
            
            creative = AdCreative(parent_id=f"act_{ad_account_id}")
            creative.update(creative_params)
            creative.remote_create()
            
            creative_id = creative['id']
            logger.info(f"Created Meta creative: {creative_id}")
            
            # Step 4: Create Ad
            ad_params = {
                'name': f"{campaign_data['name']} - Ad",
                'adset_id': adset_id,
                'creative': {'creative_id': creative_id},
                'status': 'PAUSED'
            }
            
            ad = Ad(parent_id=f"act_{ad_account_id}")
            ad.update(ad_params)
            ad.remote_create()
            
            ad_id = ad['id']
            logger.info(f"Created Meta ad: {ad_id}")
            
            return {
                'success': True,
                'campaign_id': meta_campaign_id,
                'adset_id': adset_id,
                'creative_id': creative_id,
                'ad_id': ad_id,
                'platform': 'meta'
            }
            
        except Exception as e:
            logger.error(f"Error launching Meta campaign: {e}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'meta'
            }
    
    async def _launch_google_campaign(self, campaign_data: Dict[str, Any], 
                                     creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """Launch campaign on Google Ads platform."""
        
        # Use simulation mode if API not properly configured
        if not self.google_ads_client or getattr(self, 'google_simulation_mode', True):
            return await self._simulate_google_launch(campaign_data, creative_data)
        
        try:
            customer_id = settings.google_ads_customer_id
            
            # Step 1: Create Campaign
            campaign_operation = self.google_ads_client.get_type("CampaignOperation")
            campaign = campaign_operation.create
            
            campaign.name = campaign_data['name']
            campaign.advertising_channel_type = self.google_ads_client.enums.AdvertisingChannelTypeEnum.SEARCH
            campaign.status = self.google_ads_client.enums.CampaignStatusEnum.PAUSED
            
            # Set budget
            campaign.campaign_budget = self._create_google_budget(campaign_data.get('budget_daily', 100))
            
            # Set bidding strategy
            campaign.manual_cpc.enhanced_cpc_enabled = True
            
            # Set dates
            if campaign_data.get('start_date'):
                campaign.start_date = campaign_data['start_date']
            if campaign_data.get('end_date'):
                campaign.end_date = campaign_data['end_date']
            
            # Create campaign
            campaign_service = self.google_ads_client.get_service("CampaignService")
            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )
            
            google_campaign_id = response.results[0].resource_name.split('/')[-1]
            logger.info(f"Created Google campaign: {google_campaign_id}")
            
            # Step 2: Create Ad Group
            ad_group_operation = self.google_ads_client.get_type("AdGroupOperation")
            ad_group = ad_group_operation.create
            
            ad_group.name = f"{campaign_data['name']} - AdGroup"
            ad_group.campaign = f"customers/{customer_id}/campaigns/{google_campaign_id}"
            ad_group.type_ = self.google_ads_client.enums.AdGroupTypeEnum.SEARCH_STANDARD
            ad_group.status = self.google_ads_client.enums.AdGroupStatusEnum.PAUSED
            ad_group.cpc_bid_micros = 200000  # $0.20 in micros
            
            ad_group_service = self.google_ads_client.get_service("AdGroupService")
            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[ad_group_operation]
            )
            
            ad_group_id = response.results[0].resource_name.split('/')[-1]
            logger.info(f"Created Google ad group: {ad_group_id}")
            
            # Step 3: Create Responsive Search Ad
            ad_operation = self.google_ads_client.get_type("AdGroupAdOperation")
            ad_group_ad = ad_operation.create
            
            ad_group_ad.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
            ad_group_ad.status = self.google_ads_client.enums.AdGroupAdStatusEnum.PAUSED
            
            # Set up responsive search ad
            responsive_search_ad = ad_group_ad.ad.responsive_search_ad
            
            # Add headlines
            headlines = creative_data.get('headlines', ['Default Headline'])
            for i, headline in enumerate(headlines[:3]):  # Max 3 headlines for now
                headline_asset = self.google_ads_client.get_type("AdTextAsset")
                headline_asset.text = headline[:30]  # Google limit
                responsive_search_ad.headlines.append(headline_asset)
            
            # Add descriptions
            descriptions = creative_data.get('descriptions', [creative_data.get('description', 'Default Description')])
            for i, description in enumerate(descriptions[:2]):  # Max 2 descriptions for now
                description_asset = self.google_ads_client.get_type("AdTextAsset")
                description_asset.text = description[:90]  # Google limit
                responsive_search_ad.descriptions.append(description_asset)
            
            # Set final URLs
            ad_group_ad.ad.final_urls.append(campaign_data.get('landing_url', 'https://example.com'))
            
            ad_group_ad_service = self.google_ads_client.get_service("AdGroupAdService")
            response = ad_group_ad_service.mutate_ad_group_ads(
                customer_id=customer_id,
                operations=[ad_operation]
            )
            
            ad_id = response.results[0].resource_name.split('/')[-1]
            logger.info(f"Created Google ad: {ad_id}")
            
            # Step 4: Add Keywords
            keywords = creative_data.get('keywords', ['marketing', 'advertising'])
            await self._add_google_keywords(customer_id, ad_group_id, keywords)
            
            return {
                'success': True,
                'campaign_id': google_campaign_id,
                'ad_group_id': ad_group_id,
                'ad_id': ad_id,
                'platform': 'google'
            }
            
        except GoogleAdsException as ex:
            logger.error(f"Google Ads API error: {ex}")
            return {
                'success': False,
                'error': str(ex),
                'platform': 'google'
            }
        except Exception as e:
            logger.error(f"Error launching Google campaign: {e}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'google'
            }
    
    def _create_google_budget(self, daily_budget: float) -> str:
        """Create a Google Ads budget."""
        try:
            budget_operation = self.google_ads_client.get_type("CampaignBudgetOperation")
            budget = budget_operation.create
            
            budget.name = f"Budget_{int(time.time())}"
            budget.delivery_method = self.google_ads_client.enums.BudgetDeliveryMethodEnum.STANDARD
            budget.amount_micros = int(daily_budget * 1000000)  # Convert to micros
            
            budget_service = self.google_ads_client.get_service("CampaignBudgetService")
            response = budget_service.mutate_campaign_budgets(
                customer_id=settings.google_ads_customer_id,
                operations=[budget_operation]
            )
            
            return response.results[0].resource_name
            
        except Exception as e:
            logger.error(f"Error creating Google budget: {e}")
            raise
    
    async def _add_google_keywords(self, customer_id: str, ad_group_id: str, keywords: List[str]):
        """Add keywords to Google Ad Group."""
        try:
            operations = []
            
            for keyword in keywords[:10]:  # Limit to 10 keywords
                ad_group_criterion_operation = self.google_ads_client.get_type("AdGroupCriterionOperation")
                ad_group_criterion = ad_group_criterion_operation.create
                
                ad_group_criterion.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
                ad_group_criterion.status = self.google_ads_client.enums.AdGroupCriterionStatusEnum.PAUSED
                ad_group_criterion.keyword.text = keyword
                ad_group_criterion.keyword.match_type = self.google_ads_client.enums.KeywordMatchTypeEnum.BROAD
                
                operations.append(ad_group_criterion_operation)
            
            if operations:
                ad_group_criterion_service = self.google_ads_client.get_service("AdGroupCriterionService")
                response = ad_group_criterion_service.mutate_ad_group_criteria(
                    customer_id=customer_id,
                    operations=operations
                )
                
                logger.info(f"Added {len(response.results)} keywords to ad group {ad_group_id}")
                
        except Exception as e:
            logger.error(f"Error adding keywords: {e}")
    
    def _map_objective_to_meta(self, objective: str) -> str:
        """Map generic objective to Meta objective."""
        mapping = {
            'conversions': 'CONVERSIONS',
            'traffic': 'LINK_CLICKS',
            'awareness': 'REACH',
            'engagement': 'ENGAGEMENT',
            'app_installs': 'APP_INSTALLS',
            'video_views': 'VIDEO_VIEWS'
        }
        return mapping.get(objective.lower(), 'CONVERSIONS')
    
    def _map_cta_to_meta(self, cta: str) -> str:
        """Map generic CTA to Meta CTA."""
        mapping = {
            'learn_more': 'LEARN_MORE',
            'shop_now': 'SHOP_NOW',
            'sign_up': 'SIGN_UP',
            'download': 'DOWNLOAD',
            'get_quote': 'GET_QUOTE',
            'contact_us': 'CONTACT_US'
        }
        return mapping.get(cta.lower().replace(' ', '_'), 'LEARN_MORE')
    
    def _build_meta_targeting(self, target_audience: Dict[str, Any]) -> Dict[str, Any]:
        """Build Meta targeting from audience data."""
        targeting = {
            'geo_locations': {
                'countries': target_audience.get('countries', ['US'])
            }
        }
        
        # Add age targeting
        if target_audience.get('age_range'):
            age_range = target_audience['age_range']
            if '-' in age_range:
                min_age, max_age = age_range.split('-')
                targeting['age_min'] = int(min_age)
                targeting['age_max'] = int(max_age)
        
        # Add interest targeting
        if target_audience.get('interests'):
            targeting['interests'] = [
                {'name': interest} for interest in target_audience['interests'][:10]
            ]
        
        # Add behavior targeting
        if target_audience.get('behaviors'):
            targeting['behaviors'] = [
                {'name': behavior} for behavior in target_audience['behaviors'][:5]
            ]
        
        return targeting
    
    async def pause_campaign(self, campaign_id: str, platform: str) -> Dict[str, Any]:
        """Pause a running campaign."""
        try:
            if platform.lower() == 'meta':
                result = await self._pause_meta_campaign(campaign_id)
            elif platform.lower() == 'google':
                result = await self._pause_google_campaign(campaign_id)
            else:
                return {'success': False, 'error': 'Unsupported platform'}
            
            if result['success']:
                await db_manager.update_campaign_status(campaign_id, 'paused')
                logger.info(f"Paused {platform} campaign: {campaign_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error pausing campaign: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _pause_meta_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Pause Meta campaign."""
        try:
            campaign = Campaign(campaign_id)
            campaign.update({'status': 'PAUSED'})
            campaign.remote_update()
            
            return {'success': True, 'platform': 'meta'}
        except Exception as e:
            return {'success': False, 'error': str(e), 'platform': 'meta'}
    
    async def _pause_google_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Pause Google campaign."""
        try:
            campaign_operation = self.google_ads_client.get_type("CampaignOperation")
            campaign = campaign_operation.update
            
            campaign.resource_name = f"customers/{settings.google_ads_customer_id}/campaigns/{campaign_id}"
            campaign.status = self.google_ads_client.enums.CampaignStatusEnum.PAUSED
            
            campaign_service = self.google_ads_client.get_service("CampaignService")
            response = campaign_service.mutate_campaigns(
                customer_id=settings.google_ads_customer_id,
                operations=[campaign_operation]
            )
            
            return {'success': True, 'platform': 'google'}
        except Exception as e:
            return {'success': False, 'error': str(e), 'platform': 'google'}
    
    async def _simulate_meta_launch(self, campaign_data: Dict[str, Any], creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate Meta campaign launch for testing without real API calls."""
        import uuid
        
        simulated_campaign_id = f"meta_sim_{uuid.uuid4().hex[:8]}"
        simulated_adset_id = f"adset_sim_{uuid.uuid4().hex[:8]}"
        simulated_ad_id = f"ad_sim_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"SIMULATED Meta campaign launch: {simulated_campaign_id}")
        
        return {
            'success': True,
            'platform': 'meta',
            'campaign_id': simulated_campaign_id,
            'adset_id': simulated_adset_id,
            'ad_id': simulated_ad_id,
            'status': 'active',
            'simulation': True,
            'message': 'Campaign simulated successfully (real Meta API not configured)'
        }
    
    async def _simulate_google_launch(self, campaign_data: Dict[str, Any], creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate Google Ads campaign launch for testing without real API calls."""
        import uuid
        
        simulated_campaign_id = f"google_sim_{uuid.uuid4().hex[:8]}"
        simulated_adgroup_id = f"adgroup_sim_{uuid.uuid4().hex[:8]}"
        simulated_ad_id = f"ad_sim_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"SIMULATED Google Ads campaign launch: {simulated_campaign_id}")
        
        return {
            'success': True,
            'platform': 'google',
            'campaign_id': simulated_campaign_id,
            'adgroup_id': simulated_adgroup_id,
            'ad_id': simulated_ad_id,
            'status': 'active',
            'simulation': True,
            'message': 'Campaign simulated successfully (real Google Ads API not configured)'
        }


# Global campaign launcher instance
campaign_launcher = CampaignLauncherAgent() 