-- Marketing Agent Database Schema for Supabase

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Campaigns table
CREATE TABLE campaigns (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('meta', 'google', 'both')),
    objective VARCHAR(100) NOT NULL,
    target_audience JSONB,
    budget_daily DECIMAL(10,2),
    budget_total DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'active', 'paused', 'completed')),
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    meta_campaign_id VARCHAR(255),
    google_campaign_id VARCHAR(255)
);

-- Ad creatives table
CREATE TABLE ad_creatives (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    headline VARCHAR(255) NOT NULL,
    description TEXT,
    call_to_action VARCHAR(50),
    image_url TEXT,
    image_prompt TEXT,
    generated_by VARCHAR(50) DEFAULT 'ai',
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'active', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by VARCHAR(255)
);

-- Performance tracking table
CREATE TABLE performance_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ctr DECIMAL(5,4) DEFAULT 0,
    cpc DECIMAL(8,2) DEFAULT 0,
    spend DECIMAL(10,2) DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    revenue DECIMAL(10,2) DEFAULT 0,
    roas DECIMAL(8,2) DEFAULT 0,
    quality_score INTEGER,
    status_color VARCHAR(10) DEFAULT 'green' CHECK (status_color IN ('green', 'yellow', 'red'))
);

-- Human approvals table
CREATE TABLE approvals (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    creative_id UUID REFERENCES ad_creatives(id) ON DELETE CASCADE,
    approval_type VARCHAR(20) NOT NULL CHECK (approval_type IN ('budget', 'creative', 'optimization')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by VARCHAR(255),
    notes TEXT,
    details JSONB
);

-- Agent execution logs
CREATE TABLE agent_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    langsmith_trace_id VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Optimization history
CREATE TABLE optimizations (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    optimization_type VARCHAR(50) NOT NULL,
    trigger_reason TEXT,
    changes_made JSONB,
    before_metrics JSONB,
    after_metrics JSONB,
    success BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_platform ON campaigns(platform);
CREATE INDEX idx_performance_logs_campaign_id ON performance_logs(campaign_id);
CREATE INDEX idx_performance_logs_timestamp ON performance_logs(timestamp DESC);
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_agent_logs_timestamp ON agent_logs(timestamp DESC);
CREATE INDEX idx_agent_logs_campaign_id ON agent_logs(campaign_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to campaigns table
CREATE TRIGGER update_campaigns_updated_at 
    BEFORE UPDATE ON campaigns 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) - Enable for all tables
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE ad_creatives ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimizations ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your authentication needs)
-- For now, allowing all operations - you can restrict based on user roles later
CREATE POLICY "Allow all operations" ON campaigns FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON ad_creatives FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON performance_logs FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON approvals FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON agent_logs FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON optimizations FOR ALL USING (true);

-- Create useful views
CREATE VIEW campaign_performance_summary AS
SELECT 
    c.id as campaign_id,
    c.name,
    c.platform,
    c.status,
    c.budget_daily,
    c.budget_total,
    COALESCE(SUM(p.impressions), 0) as total_impressions,
    COALESCE(SUM(p.clicks), 0) as total_clicks,
    COALESCE(AVG(p.ctr), 0) as avg_ctr,
    COALESCE(AVG(p.cpc), 0) as avg_cpc,
    COALESCE(SUM(p.spend), 0) as total_spend,
    COALESCE(SUM(p.conversions), 0) as total_conversions,
    COALESCE(SUM(p.revenue), 0) as total_revenue,
    COALESCE(AVG(p.roas), 0) as avg_roas
FROM campaigns c
LEFT JOIN performance_logs p ON c.id = p.campaign_id
GROUP BY c.id, c.name, c.platform, c.status, c.budget_daily, c.budget_total; 