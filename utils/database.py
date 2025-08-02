"""Database utilities for Supabase integration."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations with Supabase."""
    
    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
    
    async def create_campaign(self, campaign_data: Dict[str, Any]) -> str:
        """Create a new campaign and return its ID."""
        try:
            campaign_data['id'] = str(uuid.uuid4())
            campaign_data['created_at'] = datetime.utcnow().isoformat()
            
            response = self.supabase.table('campaigns').insert(campaign_data).execute()
            
            if response.data:
                logger.info(f"Created campaign: {response.data[0]['id']}")
                return response.data[0]['id']
            else:
                raise Exception("Failed to create campaign")
                
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            raise
    
    async def update_campaign_status(self, campaign_id: str, status: str) -> bool:
        """Update campaign status."""
        try:
            response = self.supabase.table('campaigns').update({
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', campaign_id).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error updating campaign status: {e}")
            return False
    
    async def create_ad_creative(self, creative_data: Dict[str, Any]) -> str:
        """Create ad creative and return its ID."""
        try:
            creative_data['id'] = str(uuid.uuid4())
            creative_data['created_at'] = datetime.utcnow().isoformat()
            
            response = self.supabase.table('ad_creatives').insert(creative_data).execute()
            
            if response.data:
                logger.info(f"Created ad creative: {response.data[0]['id']}")
                return response.data[0]['id']
            else:
                raise Exception("Failed to create ad creative")
                
        except Exception as e:
            logger.error(f"Error creating ad creative: {e}")
            raise
    
    async def log_performance(self, performance_data: Dict[str, Any]) -> bool:
        """Log performance metrics."""
        try:
            performance_data['id'] = str(uuid.uuid4())
            performance_data['timestamp'] = datetime.utcnow().isoformat()
            
            # Calculate status color based on thresholds
            ctr = performance_data.get('ctr', 0)
            cpc = performance_data.get('cpc', 0)
            roas = performance_data.get('roas', 0)
            
            if ctr < settings.ctr_threshold or cpc > settings.cpc_threshold or roas < settings.roas_threshold:
                performance_data['status_color'] = 'red'
            elif ctr < settings.ctr_threshold * 1.5 or cpc > settings.cpc_threshold * 0.8:
                performance_data['status_color'] = 'yellow'
            else:
                performance_data['status_color'] = 'green'
            
            response = self.supabase.table('performance_logs').insert(performance_data).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error logging performance: {e}")
            return False
    
    async def log_agent_execution(self, agent_name: str, campaign_id: str, action: str, 
                                  status: str, input_data: Dict = None, output_data: Dict = None,
                                  error_message: str = None, execution_time_ms: int = None,
                                  langsmith_trace_id: str = None) -> bool:
        """Log agent execution details."""
        try:
            log_data = {
                'id': str(uuid.uuid4()),
                'agent_name': agent_name,
                'campaign_id': campaign_id,
                'action': action,
                'status': status,
                'input_data': input_data,
                'output_data': output_data,
                'error_message': error_message,
                'execution_time_ms': execution_time_ms,
                'langsmith_trace_id': langsmith_trace_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table('agent_logs').insert(log_data).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error logging agent execution: {e}")
            return False
    
    async def request_approval(self, campaign_id: str, creative_id: str, 
                              approval_type: str, details: Dict[str, Any]) -> str:
        """Request human approval."""
        try:
            approval_data = {
                'id': str(uuid.uuid4()),
                'campaign_id': campaign_id,
                'creative_id': creative_id,
                'approval_type': approval_type,
                'status': 'pending',
                'details': details,
                'requested_at': datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table('approvals').insert(approval_data).execute()
            
            if response.data:
                logger.info(f"Created approval request: {response.data[0]['id']}")
                return response.data[0]['id']
            else:
                raise Exception("Failed to create approval request")
                
        except Exception as e:
            logger.error(f"Error requesting approval: {e}")
            raise
    
    async def check_approval_status(self, approval_id: str) -> Optional[str]:
        """Check the status of an approval request."""
        try:
            response = self.supabase.table('approvals').select('status').eq('id', approval_id).execute()
            
            if response.data:
                return response.data[0]['status']
            return None
            
        except Exception as e:
            logger.error(f"Error checking approval status: {e}")
            return None
    
    async def update_approval_status(self, approval_id: str, status: str, 
                                   approved_by: str = None, notes: str = None) -> bool:
        """Update approval status."""
        try:
            update_data = {
                'status': status,
                'approved_at': datetime.utcnow().isoformat(),
                'approved_by': approved_by,
                'notes': notes
            }
            
            response = self.supabase.table('approvals').update(update_data).eq('id', approval_id).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error updating approval status: {e}")
            return False
    
    async def update_campaign_budget(self, campaign_id: str, budget_daily: float = None, 
                                   budget_total: float = None) -> bool:
        """Update campaign budget."""
        try:
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            
            if budget_daily is not None:
                update_data['budget_daily'] = budget_daily
            if budget_total is not None:
                update_data['budget_total'] = budget_total
            
            response = self.supabase.table('campaigns').update(update_data).eq('id', campaign_id).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error updating campaign budget: {e}")
            return False
    
    async def get_campaign_performance(self, campaign_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get campaign performance for the last N hours."""
        try:
            # Calculate timestamp for N hours ago
            from datetime import timedelta
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            response = self.supabase.table('performance_logs').select('*').eq(
                'campaign_id', campaign_id
            ).gte('timestamp', cutoff_time).order('timestamp', desc=True).execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error getting campaign performance: {e}")
            return []
    
    async def get_active_campaigns(self) -> List[Dict[str, Any]]:
        """Get all active campaigns."""
        try:
            response = self.supabase.table('campaigns').select('*').eq('status', 'active').execute()
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error getting active campaigns: {e}")
            return []
    
    async def log_optimization(self, campaign_id: str, optimization_type: str,
                              trigger_reason: str, changes_made: Dict[str, Any],
                              before_metrics: Dict[str, Any], after_metrics: Dict[str, Any] = None,
                              success: bool = False) -> bool:
        """Log optimization actions."""
        try:
            optimization_data = {
                'id': str(uuid.uuid4()),
                'campaign_id': campaign_id,
                'optimization_type': optimization_type,
                'trigger_reason': trigger_reason,
                'changes_made': changes_made,
                'before_metrics': before_metrics,
                'after_metrics': after_metrics,
                'success': success,
                'created_at': datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table('optimizations').insert(optimization_data).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error logging optimization: {e}")
            return False


    async def get_all_campaigns(self) -> List[Dict[str, Any]]:
        """Get all campaigns."""
        try:
            response = self.supabase.table('campaigns').select('*').order('created_at', desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting all campaigns: {e}")
            return []
    
    async def get_campaign_by_id(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get campaign by ID."""
        try:
            response = self.supabase.table('campaigns').select('*').eq('id', campaign_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting campaign by ID: {e}")
            return None
    
    async def get_campaign_creatives(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get all ad creatives for a campaign."""
        try:
            response = self.supabase.table('ad_creatives').select('*').eq('campaign_id', campaign_id).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting campaign creatives: {e}")
            return []
    
    async def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign and all related data (cascaded by database constraints)."""
        try:
            # First verify the campaign exists
            campaign = await self.get_campaign_by_id(campaign_id)
            if not campaign:
                logger.warning(f"Campaign {campaign_id} not found for deletion")
                return False
            
            # Delete the campaign (related data will be deleted automatically via CASCADE)
            response = self.supabase.table('campaigns').delete().eq('id', campaign_id).execute()
            
            if response.data:
                logger.info(f"Successfully deleted campaign: {campaign_id} ({campaign['name']})")
                return True
            else:
                logger.error(f"Failed to delete campaign: {campaign_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting campaign {campaign_id}: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager() 