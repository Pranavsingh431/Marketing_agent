"""Budget Controller Agent for managing campaign budgets and preventing overspend."""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from config import settings
from utils.database import db_manager

logger = logging.getLogger(__name__)


class BudgetControllerAgent:
    """Agent responsible for budget management and overspend prevention."""
    
    def __init__(self):
        self.daily_budget_checks = {}  # Cache for budget tracking
        self.alert_thresholds = {
            'warning': 0.80,  # 80% of budget spent
            'critical': 0.90,  # 90% of budget spent
            'emergency': 0.95   # 95% of budget spent
        }
    
    async def check_all_campaign_budgets(self) -> Dict[str, Any]:
        """Check budgets for all active campaigns."""
        start_time = time.time()
        
        try:
            # Get all active campaigns
            active_campaigns = await db_manager.get_active_campaigns()
            
            if not active_campaigns:
                return {'success': True, 'campaigns_checked': 0}
            
            budget_reports = []
            actions_taken = []
            
            for campaign in active_campaigns:
                try:
                    budget_status = await self._check_campaign_budget(campaign)
                    budget_reports.append(budget_status)
                    
                    # Take action if needed
                    if budget_status['needs_action']:
                        action_result = await self._handle_budget_alert(campaign, budget_status)
                        actions_taken.append(action_result)
                        
                except Exception as e:
                    logger.error(f"Error checking budget for campaign {campaign['id']}: {e}")
                    continue
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log budget check execution
            await db_manager.log_agent_execution(
                agent_name="BudgetController",
                campaign_id=None,  # Multiple campaigns
                action="check_all_budgets",
                status="completed",
                input_data={'campaigns_count': len(active_campaigns)},
                output_data={
                    'budget_reports': len(budget_reports),
                    'actions_taken': len(actions_taken)
                },
                execution_time_ms=execution_time
            )
            
            logger.info(f"Checked budgets for {len(budget_reports)} campaigns in {execution_time}ms")
            
            return {
                'success': True,
                'campaigns_checked': len(budget_reports),
                'budget_reports': budget_reports,
                'actions_taken': actions_taken,
                'execution_time_ms': execution_time
            }
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"Error checking campaign budgets: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'execution_time_ms': execution_time
            }
    
    async def _check_campaign_budget(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        """Check budget status for a specific campaign."""
        
        campaign_id = campaign['id']
        daily_budget = campaign.get('budget_daily', 0)
        total_budget = campaign.get('budget_total', None)
        
        # Get today's spending
        today = datetime.now().date()
        daily_performance = await db_manager.get_campaign_performance(campaign_id, hours=24)
        
        daily_spend = sum(log.get('spend', 0) for log in daily_performance)
        
        # Get total spending if total budget is set
        total_spend = 0
        if total_budget:
            # Get all-time spending for this campaign
            all_performance = await db_manager.get_campaign_performance(campaign_id, hours=24*365)  # Year
            total_spend = sum(log.get('spend', 0) for log in all_performance)
        
        # Calculate budget utilization
        daily_utilization = (daily_spend / daily_budget) if daily_budget > 0 else 0
        total_utilization = (total_spend / total_budget) if total_budget and total_budget > 0 else 0
        
        # Determine alert level
        alert_level = None
        needs_action = False
        
        # Check daily budget
        if daily_utilization >= self.alert_thresholds['emergency']:
            alert_level = 'emergency'
            needs_action = True
        elif daily_utilization >= self.alert_thresholds['critical']:
            alert_level = 'critical'
            needs_action = True
        elif daily_utilization >= self.alert_thresholds['warning']:
            alert_level = 'warning'
        
        # Check total budget if applicable
        if total_budget and total_utilization >= self.alert_thresholds['emergency']:
            alert_level = 'emergency'
            needs_action = True
        elif total_budget and total_utilization >= self.alert_thresholds['critical']:
            if alert_level != 'emergency':
                alert_level = 'critical'
                needs_action = True
        
        # Check against global daily limit
        if daily_spend > settings.daily_budget_limit:
            alert_level = 'emergency'
            needs_action = True
        
        budget_status = {
            'campaign_id': campaign_id,
            'campaign_name': campaign.get('name', 'Unknown'),
            'daily_budget': daily_budget,
            'daily_spend': daily_spend,
            'daily_utilization': daily_utilization,
            'total_budget': total_budget,
            'total_spend': total_spend,
            'total_utilization': total_utilization,
            'alert_level': alert_level,
            'needs_action': needs_action,
            'remaining_daily_budget': max(0, daily_budget - daily_spend),
            'remaining_total_budget': max(0, total_budget - total_spend) if total_budget else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Log budget status if there are alerts
        if alert_level:
            logger.warning(f"Budget alert for campaign {campaign_id}: {alert_level} - "
                         f"Daily: {daily_utilization:.1%} ({daily_spend:.2f}/${daily_budget})")
            
            if total_budget:
                logger.warning(f"Total budget utilization: {total_utilization:.1%} "
                             f"({total_spend:.2f}/${total_budget})")
        
        return budget_status
    
    async def _handle_budget_alert(self, campaign: Dict[str, Any], 
                                  budget_status: Dict[str, Any]) -> Dict[str, Any]:
        """Handle budget alerts by taking appropriate actions."""
        
        campaign_id = campaign['id']
        alert_level = budget_status['alert_level']
        
        actions_taken = []
        
        try:
            if alert_level == 'emergency':
                # Pause campaign immediately
                pause_result = await self._pause_campaign_for_budget(campaign_id)
                actions_taken.append({
                    'action': 'pause_campaign',
                    'reason': 'Emergency budget threshold reached',
                    'success': pause_result['success'],
                    'details': pause_result
                })
                
                # Request immediate human approval for budget increase
                approval_result = await self._request_budget_approval(
                    campaign_id, 'emergency', budget_status
                )
                actions_taken.append({
                    'action': 'request_emergency_approval',
                    'reason': 'Campaign paused due to budget emergency',
                    'success': approval_result['success'],
                    'approval_id': approval_result.get('approval_id')
                })
                
            elif alert_level == 'critical':
                # Reduce bid amounts to slow spending
                bid_result = await self._reduce_campaign_bids(campaign_id, reduction=0.20)
                actions_taken.append({
                    'action': 'reduce_bids',
                    'reason': 'Critical budget threshold reached',
                    'success': bid_result['success'],
                    'reduction': '20%'
                })
                
                # Request human approval for budget adjustment
                approval_result = await self._request_budget_approval(
                    campaign_id, 'budget_increase', budget_status
                )
                actions_taken.append({
                    'action': 'request_budget_approval',
                    'reason': 'Critical budget utilization',
                    'success': approval_result['success'],
                    'approval_id': approval_result.get('approval_id')
                })
                
            elif alert_level == 'warning':
                # Send notification but continue running
                notification_result = await self._send_budget_notification(
                    campaign_id, 'warning', budget_status
                )
                actions_taken.append({
                    'action': 'send_notification',
                    'reason': 'Warning budget threshold reached',
                    'success': notification_result['success']
                })
            
            # Log the budget action
            await db_manager.log_agent_execution(
                agent_name="BudgetController",
                campaign_id=campaign_id,
                action="handle_budget_alert",
                status="completed",
                input_data={'alert_level': alert_level, 'budget_status': budget_status},
                output_data={'actions_taken': actions_taken}
            )
            
            return {
                'success': True,
                'campaign_id': campaign_id,
                'alert_level': alert_level,
                'actions_taken': actions_taken
            }
            
        except Exception as e:
            error_msg = f"Error handling budget alert: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'campaign_id': campaign_id,
                'alert_level': alert_level,
                'error': error_msg,
                'actions_taken': actions_taken
            }
    
    async def _pause_campaign_for_budget(self, campaign_id: str) -> Dict[str, Any]:
        """Pause campaign due to budget emergency."""
        
        try:
            # Update campaign status in database
            success = await db_manager.update_campaign_status(campaign_id, 'paused')
            
            if success:
                logger.info(f"Paused campaign {campaign_id} due to budget emergency")
                
                # Here you would also pause on the ad platforms
                # For now, we'll just update the database status
                
                return {
                    'success': True,
                    'message': 'Campaign paused successfully',
                    'reason': 'Budget emergency threshold reached'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to update campaign status'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _reduce_campaign_bids(self, campaign_id: str, reduction: float) -> Dict[str, Any]:
        """Reduce campaign bids to slow spending."""
        
        try:
            # In a real implementation, you would call the platform APIs to reduce bids
            # For now, we'll simulate this action
            
            logger.info(f"Reduced bids for campaign {campaign_id} by {reduction:.1%}")
            
            return {
                'success': True,
                'message': f'Bids reduced by {reduction:.1%}',
                'reduction_amount': reduction
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _request_budget_approval(self, campaign_id: str, approval_type: str, 
                                     budget_status: Dict[str, Any]) -> Dict[str, Any]:
        """Request human approval for budget adjustments."""
        
        try:
            approval_details = {
                'current_budget_status': budget_status,
                'requested_action': approval_type,
                'urgency': budget_status['alert_level'],
                'recommended_budget_increase': self._calculate_recommended_budget_increase(budget_status)
            }
            
            approval_id = await db_manager.request_approval(
                campaign_id=campaign_id,
                creative_id=None,  # Budget approval doesn't need creative
                approval_type=approval_type,
                details=approval_details
            )
            
            return {
                'success': True,
                'approval_id': approval_id,
                'details': approval_details
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_recommended_budget_increase(self, budget_status: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate recommended budget increase based on performance."""
        
        daily_utilization = budget_status['daily_utilization']
        current_daily_budget = budget_status['daily_budget']
        
        # Calculate recommended increase based on utilization rate
        if daily_utilization > 0.95:
            recommended_increase = 0.50  # 50% increase for emergency
        elif daily_utilization > 0.90:
            recommended_increase = 0.30  # 30% increase for critical
        else:
            recommended_increase = 0.20  # 20% increase for warning
        
        new_daily_budget = current_daily_budget * (1 + recommended_increase)
        
        return {
            'current_daily_budget': current_daily_budget,
            'recommended_daily_budget': new_daily_budget,
            'increase_percentage': recommended_increase,
            'increase_amount': new_daily_budget - current_daily_budget,
            'justification': f'Based on {daily_utilization:.1%} budget utilization'
        }
    
    async def _send_budget_notification(self, campaign_id: str, level: str, 
                                      budget_status: Dict[str, Any]) -> Dict[str, Any]:
        """Send budget notification."""
        
        try:
            # In a real implementation, you would send email/Slack/SMS notifications
            # For now, we'll just log the notification
            
            logger.info(f"Budget notification sent for campaign {campaign_id}: {level}")
            
            notification_data = {
                'campaign_id': campaign_id,
                'level': level,
                'budget_status': budget_status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Could integrate with notification services here
            
            return {
                'success': True,
                'notification_sent': True,
                'data': notification_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def adjust_campaign_budget(self, campaign_id: str, new_daily_budget: float, 
                                   new_total_budget: Optional[float] = None, 
                                   reason: str = "Manual adjustment") -> Dict[str, Any]:
        """Manually adjust campaign budget."""
        
        try:
            # Get current campaign
            campaigns = await db_manager.get_active_campaigns()
            campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
            
            if not campaign:
                return {'success': False, 'error': 'Campaign not found'}
            
            old_daily_budget = campaign.get('budget_daily', 0)
            old_total_budget = campaign.get('budget_total', None)
            
            # Update budget in database (you'd need to implement this method)
            # For now, we'll simulate the update
            
            budget_change = {
                'campaign_id': campaign_id,
                'old_daily_budget': old_daily_budget,
                'new_daily_budget': new_daily_budget,
                'old_total_budget': old_total_budget,
                'new_total_budget': new_total_budget,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Log budget adjustment
            await db_manager.log_optimization(
                campaign_id=campaign_id,
                optimization_type='budget_adjustment',
                trigger_reason=reason,
                changes_made=budget_change,
                before_metrics={'daily_budget': old_daily_budget, 'total_budget': old_total_budget},
                after_metrics={'daily_budget': new_daily_budget, 'total_budget': new_total_budget},
                success=True
            )
            
            logger.info(f"Budget adjusted for campaign {campaign_id}: "
                       f"${old_daily_budget} -> ${new_daily_budget} daily")
            
            return {
                'success': True,
                'budget_change': budget_change,
                'message': 'Budget updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_budget_summary(self, campaign_id: Optional[str] = None) -> Dict[str, Any]:
        """Get budget summary for campaign(s)."""
        
        try:
            if campaign_id:
                # Get specific campaign
                campaigns = await db_manager.get_active_campaigns()
                campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
                if not campaign:
                    return {'success': False, 'error': 'Campaign not found'}
                campaigns_to_check = [campaign]
            else:
                # Get all active campaigns
                campaigns_to_check = await db_manager.get_active_campaigns()
            
            budget_summaries = []
            total_daily_budget = 0
            total_daily_spend = 0
            
            for campaign in campaigns_to_check:
                budget_status = await self._check_campaign_budget(campaign)
                budget_summaries.append(budget_status)
                
                total_daily_budget += budget_status['daily_budget']
                total_daily_spend += budget_status['daily_spend']
            
            overall_utilization = (total_daily_spend / total_daily_budget) if total_daily_budget > 0 else 0
            
            return {
                'success': True,
                'summary': {
                    'total_daily_budget': total_daily_budget,
                    'total_daily_spend': total_daily_spend,
                    'overall_utilization': overall_utilization,
                    'campaigns_count': len(budget_summaries),
                    'campaigns_with_alerts': len([b for b in budget_summaries if b['alert_level']]),
                    'timestamp': datetime.utcnow().isoformat()
                },
                'campaign_budgets': budget_summaries
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# Global budget controller instance
budget_controller = BudgetControllerAgent() 