"""Main FastAPI application for the Marketing Agent system."""

import logging
import asyncio
import warnings
from datetime import datetime
from typing import Dict, List, Any, Optional

# Suppress urllib3 SSL warnings that are just compatibility notices
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL 1.1.1+")
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import structlog

from config import settings
from utils.database import db_manager
from agents.content_generator import content_generator
from agents.simple_generator import simple_generator
from agents.visual_creator import visual_creator
from agents.campaign_launcher import campaign_launcher
from agents.performance_tracker import performance_tracker
from agents.optimizer import optimizer
from agents.budget_controller import budget_controller

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Marketing Agent API",
    description="Production-grade multi-agent marketing automation system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create generated_images directory if it doesn't exist
os.makedirs('generated_images', exist_ok=True)

# Mount static files for serving generated images  
app.mount("/images", StaticFiles(directory="generated_images"), name="images")

# Serve dashboard HTML file
@app.get("/", response_class=FileResponse)
async def get_dashboard_html():
    """Serve the dashboard HTML file."""
    return FileResponse("dashboard.html")

# Pydantic models for API
class CampaignRequest(BaseModel):
    name: str
    product_name: str
    product_description: str
    product_category: Optional[str] = None
    product_features: Optional[str] = None
    product_price: Optional[str] = None
    objective: str = "conversions"
    platform: str = "meta"  # "meta", "google", or "both"
    budget_daily: float
    budget_total: Optional[float] = None
    target_audience: Dict[str, Any] = {}
    landing_url: str = "https://example.com"
    brand_tone: Optional[str] = "friendly"
    selling_points: Optional[str] = None
    special_offers: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ApprovalRequest(BaseModel):
    approval_id: str
    action: str  # "approve" or "reject"
    notes: Optional[str] = None

class OptimizationRequest(BaseModel):
    campaign_id: str
    force_optimization: bool = False


# Global background task for continuous tracking
continuous_tracking_task = None


@app.on_event("startup")
async def startup_event():
    """Initialize the application and start background tasks."""
    logger.info("Starting Marketing Agent API")
    
    # Start continuous performance tracking
    global continuous_tracking_task
    continuous_tracking_task = asyncio.create_task(
        performance_tracker.start_continuous_tracking(interval_minutes=60)
    )
    
    logger.info("Marketing Agent API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources."""
    logger.info("Shutting down Marketing Agent API")
    
    # Cancel background tasks
    if continuous_tracking_task:
        continuous_tracking_task.cancel()
        try:
            await continuous_tracking_task
        except asyncio.CancelledError:
            pass
    
    logger.info("Marketing Agent API shut down complete")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Marketing Agent API",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment
    }


@app.post("/campaigns/create")
async def create_campaign(campaign_request: CampaignRequest, background_tasks: BackgroundTasks):
    """Create and launch a new marketing campaign."""
    try:
        logger.info("Creating new campaign", campaign_name=campaign_request.name)
        
        # Step 1: Create campaign in database
        campaign_data = campaign_request.dict()
        
        # Remove fields not in database schema - only keep columns that exist in campaigns table
        db_columns = ['name', 'platform', 'objective', 'target_audience', 'budget_daily', 'budget_total', 'status', 'start_date', 'end_date']
        db_campaign_data = {k: v for k, v in campaign_data.items() if k in db_columns}
        campaign_id = await db_manager.create_campaign(db_campaign_data)
        campaign_data['campaign_id'] = campaign_id
        
        # Step 2: Generate content
        logger.info("Generating content", campaign_id=campaign_id)
        # Try main generator first, fallback to simple if needed
        logger.info("Generating content with main generator...")
        try:
            content_result = await content_generator.generate_ad_copy(campaign_data)
        except Exception as e:
            logger.warning(f"Main generator failed: {e}, using simple generator...")
            content_result = await simple_generator.generate_simple_ad_copy(campaign_data)
        
        if not content_result['success']:
            raise HTTPException(status_code=500, detail=f"Content generation failed: {content_result['error']}")
        
        content_data = content_result['content']
        
        # Step 3: Generate image
        logger.info("Generating image", campaign_id=campaign_id)
        image_result = await visual_creator.generate_ad_image(campaign_data, content_data)
        
        if image_result['success']:
            content_data['image_url'] = image_result['image_url']
            content_data['image_prompt'] = image_result['image_prompt']
        else:
            logger.warning("Image generation failed", error=image_result['error'])
        
        # Step 4: Create ad creative in database
        creative_data = {
            'campaign_id': campaign_id,
            'headline': content_data.get('headlines', [''])[0],
            'description': content_data.get('description', ''),
            'call_to_action': content_data.get('call_to_action', 'Learn More'),
            'image_url': content_data.get('image_url'),
            'image_prompt': content_data.get('image_prompt'),
            'status': 'pending_approval' if settings.human_approval_required else 'approved'
        }
        
        creative_id = await db_manager.create_ad_creative(creative_data)
        
        # Step 5: Request approval if required
        approval_id = None
        if settings.human_approval_required:
            approval_id = await db_manager.request_approval(
                campaign_id=campaign_id,
                creative_id=creative_id,
                approval_type='creative',
                details={
                    'content': content_data,
                    'budget_daily': campaign_request.budget_daily,
                    'platform': campaign_request.platform
                }
            )
            
            await db_manager.update_campaign_status(campaign_id, 'pending_approval')
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "creative_id": creative_id,
                "approval_id": approval_id,
                "status": "pending_approval",
                "message": "Campaign created and pending approval",
                "content": content_data
            }
        
        # Step 6: Launch campaign immediately if no approval required
        background_tasks.add_task(launch_approved_campaign, campaign_data, content_data)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "creative_id": creative_id,
            "status": "launching",
            "message": "Campaign created and launching",
            "content": content_data
        }
        
    except Exception as e:
        logger.error("Error creating campaign", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approvals/respond")
async def respond_to_approval(approval_request: ApprovalRequest, background_tasks: BackgroundTasks):
    """Respond to a human approval request."""
    try:
        approval_id = approval_request.approval_id
        action = approval_request.action
        
        logger.info("Processing approval response", approval_id=approval_id, action=action)
        
        # Update approval status in database
        # This would require adding an update_approval_status method to db_manager
        # For now, we'll simulate the response
        
        if action == "approve":
            # Get approval details and launch campaign
            # This is a simplified version - you'd need to implement the full flow
            return {
                "success": True,
                "message": "Campaign approved and launching",
                "approval_id": approval_id
            }
        else:
            return {
                "success": True,
                "message": "Campaign rejected",
                "approval_id": approval_id
            }
            
    except Exception as e:
        logger.error("Error processing approval", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns/{campaign_id}/performance")
async def get_campaign_performance(campaign_id: str, hours: int = 24):
    """Get performance summary for a campaign."""
    try:
        summary = await performance_tracker.get_campaign_performance_summary(campaign_id, hours)
        
        if not summary['success']:
            raise HTTPException(status_code=404, detail=summary['error'])
        
        return summary
        
    except Exception as e:
        logger.error("Error getting campaign performance", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/campaigns/{campaign_id}/optimize")
async def optimize_campaign(campaign_id: str, optimization_request: OptimizationRequest, background_tasks: BackgroundTasks):
    """Trigger campaign optimization."""
    try:
        logger.info("Triggering campaign optimization", campaign_id=campaign_id)
        
        # Get current performance data
        performance_summary = await performance_tracker.get_campaign_performance_summary(campaign_id, 24)
        
        if not performance_summary['success']:
            raise HTTPException(status_code=404, detail="Campaign performance data not found")
        
        # Check if optimization is needed
        metrics = performance_summary['metrics']
        status = performance_summary['status']
        
        if status == 'green' and not optimization_request.force_optimization:
            return {
                "success": True,
                "message": "Campaign performance is healthy, no optimization needed",
                "status": status,
                "metrics": metrics
            }
        
        # Trigger optimization in background
        background_tasks.add_task(optimize_campaign_performance, campaign_id, metrics)
        
        return {
            "success": True,
            "message": "Campaign optimization triggered",
            "status": status,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error("Error triggering optimization", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause a running campaign."""
    try:
        # This would require getting campaign platform info from database
        # For now, we'll assume it's a meta campaign
        result = await campaign_launcher.pause_campaign(campaign_id, 'meta')
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return {
            "success": True,
            "message": "Campaign paused successfully",
            "campaign_id": campaign_id
        }
        
    except Exception as e:
        logger.error("Error pausing campaign", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns")
async def list_campaigns():
    """Get all campaigns."""
    try:
        campaigns = await db_manager.get_all_campaigns()
        return {"campaigns": campaigns}
    except Exception as e:
        logger.error("Error fetching campaigns", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get specific campaign details."""
    try:
        campaign = await db_manager.get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return campaign
    except Exception as e:
        logger.error("Error fetching campaign", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """Delete a specific campaign and all related data."""
    try:
        success = await db_manager.delete_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found or could not be deleted")
        
        logger.info(f"Campaign {campaign_id} deleted successfully")
        return {
            "success": True, 
            "message": f"Campaign {campaign_id} deleted successfully",
            "campaign_id": campaign_id
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error("Error deleting campaign", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {str(e)}")


@app.get("/dashboard")
async def get_dashboard_data():
    """Get dashboard data with overview of all campaigns."""
    try:
        # Get active campaigns
        active_campaigns = await db_manager.get_active_campaigns()
        
        dashboard_data = {
            "total_campaigns": len(active_campaigns),
            "active_campaigns": [],
            "summary_metrics": {
                "total_spend": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "total_conversions": 0,
                "avg_ctr": 0,
                "avg_cpc": 0,
                "avg_roas": 0
            }
        }
        
        # Get performance data and AI content for each campaign
        for campaign in active_campaigns:
            campaign_id = campaign['id']
            
            # Get AI-generated creative content for this campaign
            creatives = await db_manager.get_campaign_creatives(campaign_id)
            
            # Get performance data (optional - may not exist for new campaigns)
            performance = await performance_tracker.get_campaign_performance_summary(campaign_id, 24)
            
            # Default metrics for new campaigns
            default_metrics = {
                'total_spend': 0,
                'total_impressions': 0,
                'total_clicks': 0,
                'total_conversions': 0,
                'total_revenue': 0,
                'avg_ctr': 0,
                'avg_cpc': 0,
                'avg_roas': 0
            }
            
            if performance['success']:
                metrics = performance['metrics']
                status = performance['status']
                # Add to summary metrics
                dashboard_data['summary_metrics']['total_spend'] += metrics['total_spend']
                dashboard_data['summary_metrics']['total_impressions'] += metrics['total_impressions']
                dashboard_data['summary_metrics']['total_clicks'] += metrics['total_clicks']
                dashboard_data['summary_metrics']['total_conversions'] += metrics['total_conversions']
            else:
                metrics = default_metrics
                status = 'active'
            
            # Always include the campaign with its AI-generated content
            campaign_summary = {
                "id": campaign_id,
                "name": campaign['name'],
                "platform": campaign['platform'],
                "status": status,
                "budget_daily": campaign.get('budget_daily', 0),
                "created_at": campaign.get('created_at'),
                "metrics": metrics,
                "ai_content": creatives[0] if creatives else None  # Include AI-generated creative content
            }
            dashboard_data['active_campaigns'].append(campaign_summary)
        
        # Calculate averages
        if dashboard_data['summary_metrics']['total_impressions'] > 0:
            dashboard_data['summary_metrics']['avg_ctr'] = (
                dashboard_data['summary_metrics']['total_clicks'] / 
                dashboard_data['summary_metrics']['total_impressions']
            )
        
        if dashboard_data['summary_metrics']['total_clicks'] > 0:
            dashboard_data['summary_metrics']['avg_cpc'] = (
                dashboard_data['summary_metrics']['total_spend'] / 
                dashboard_data['summary_metrics']['total_clicks']
            )
        
        if dashboard_data['summary_metrics']['total_spend'] > 0:
            dashboard_data['summary_metrics']['avg_roas'] = (
                sum(c['metrics']['total_revenue'] for c in dashboard_data['active_campaigns']) /
                dashboard_data['summary_metrics']['total_spend']
            )
        
        return dashboard_data
        
    except Exception as e:
        logger.error("Error getting dashboard data", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/campaigns/track")
async def track_all_campaigns():
    """Manual trigger for performance tracking (used by scheduler)."""
    try:
        result = await performance_tracker.track_all_campaigns()
        return result
        
    except Exception as e:
        logger.error("Error in manual tracking trigger", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/budgets/check")
async def check_all_budgets():
    """Manual trigger for budget checking (used by scheduler)."""
    try:
        result = await budget_controller.check_all_campaign_budgets()
        return result
        
    except Exception as e:
        logger.error("Error in manual budget check", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/budgets/summary")
async def get_budget_summary(campaign_id: Optional[str] = None):
    """Get budget summary for all campaigns or a specific campaign."""
    try:
        result = await budget_controller.get_budget_summary(campaign_id)
        
        if not result['success']:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return result
        
    except Exception as e:
        logger.error("Error getting budget summary", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/budgets/adjust/{campaign_id}")
async def adjust_campaign_budget(
    campaign_id: str,
    new_daily_budget: float,
    new_total_budget: Optional[float] = None,
    reason: str = "Manual adjustment"
):
    """Manually adjust campaign budget."""
    try:
        result = await budget_controller.adjust_campaign_budget(
            campaign_id, new_daily_budget, new_total_budget, reason
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except Exception as e:
        logger.error("Error adjusting budget", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/campaigns/{campaign_id}/force-optimize")
async def force_optimize_campaign(campaign_id: str, background_tasks: BackgroundTasks):
    """Force immediate optimization of a campaign."""
    try:
        # Get current performance data
        performance_summary = await performance_tracker.get_campaign_performance_summary(campaign_id, 24)
        
        if not performance_summary['success']:
            raise HTTPException(status_code=404, detail="Campaign performance data not found")
        
        # Trigger comprehensive optimization
        optimization_result = await optimizer.optimize_campaign(
            campaign_id,
            performance_summary['metrics'],
            'Manual optimization request'
        )
        
        return optimization_result
        
    except Exception as e:
        logger.error("Error in forced optimization", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Background task functions
async def launch_approved_campaign(campaign_data: Dict[str, Any], content_data: Dict[str, Any]):
    """Launch an approved campaign."""
    try:
        logger.info("Launching approved campaign", campaign_id=campaign_data['campaign_id'])
        
        result = await campaign_launcher.launch_campaign(campaign_data, content_data)
        
        if result['success']:
            logger.info("Campaign launched successfully", campaign_id=campaign_data['campaign_id'])
        else:
            logger.error("Campaign launch failed", campaign_id=campaign_data['campaign_id'], error=result['error'])
            
    except Exception as e:
        logger.error("Error in background campaign launch", error=str(e))


async def optimize_campaign_performance(campaign_id: str, current_metrics: Dict[str, Any]):
    """Optimize campaign performance based on current metrics."""
    try:
        logger.info("Starting campaign optimization", campaign_id=campaign_id)
        
        # Use the comprehensive optimizer
        result = await optimizer.optimize_campaign(
            campaign_id,
            current_metrics,
            'Background optimization triggered by performance monitoring'
        )
        
        if result['success']:
            logger.info("Campaign optimization completed", campaign_id=campaign_id)
        else:
            logger.error("Campaign optimization failed", campaign_id=campaign_id, error=result.get('error'))
        
    except Exception as e:
        logger.error("Error in campaign optimization", campaign_id=campaign_id, error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    ) 