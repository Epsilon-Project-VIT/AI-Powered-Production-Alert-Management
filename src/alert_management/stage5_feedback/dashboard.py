"""
Dashboard Generator.

Generates HTML dashboards with performance metrics and visualizations.
"""

from typing import List, Optional
from datetime import datetime
from pathlib import Path

from .schemas import FeedbackRecord
from .metrics import MetricsCalculator, SystemMetrics, Stage2Metrics, Stage3Metrics, Stage4Metrics


class DashboardGenerator:
    """Generate HTML performance dashboard."""
    
    def __init__(self):
        """Initialize dashboard generator."""
        self.metrics_calculator = MetricsCalculator()
    
    def generate_dashboard(
        self,
        feedbacks: List[FeedbackRecord],
        start_date: datetime,
        end_date: datetime,
        output_file: Path
    ) -> None:
        """
        Generate HTML dashboard with metrics and visualizations.
        
        Args:
            feedbacks: List of feedback records
            start_date: Start of reporting period
            end_date: End of reporting period
            output_file: Path to output HTML file
        """
        # Calculate all metrics
        system_metrics = self.metrics_calculator.calculate_system_metrics(
            feedbacks, start_date, end_date
        )
        stage2_metrics = self.metrics_calculator.calculate_stage2_metrics(feedbacks)
        stage3_metrics = self.metrics_calculator.calculate_stage3_metrics(feedbacks)
        stage4_metrics = self.metrics_calculator.calculate_stage4_metrics(feedbacks)
        
        # Generate HTML
        html = self._generate_html(
            system_metrics,
            stage2_metrics,
            stage3_metrics,
            stage4_metrics,
            start_date,
            end_date
        )
        
        # Write to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html)
    
    def _generate_html(
        self,
        system_metrics: SystemMetrics,
        stage2_metrics: Optional[Stage2Metrics],
        stage3_metrics: Optional[Stage3Metrics],
        stage4_metrics: Optional[Stage4Metrics],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate HTML content."""
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Alert Management - Performance Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 20px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 5px;
        }}
        
        .date-range {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }}
        
        .metric-card.success {{
            border-left-color: #27ae60;
        }}
        
        .metric-card.warning {{
            border-left-color: #f39c12;
        }}
        
        .metric-card.danger {{
            border-left-color: #e74c3c;
        }}
        
        .metric-label {{
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }}
        
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #2c3e50;
        }}
        
        .metric-subtitle {{
            font-size: 14px;
            color: #95a5a6;
            margin-top: 5px;
        }}
        
        .stage-section {{
            margin-bottom: 40px;
            padding: 20px;
            background: #fafafa;
            border-radius: 6px;
        }}
        
        .metrics-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        .metrics-table th,
        .metrics-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .metrics-table th {{
            background: #34495e;
            color: white;
            font-weight: 600;
        }}
        
        .metrics-table tr:hover {{
            background: #f8f9fa;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 20px;
            background: #ecf0f1;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #3498db, #2980b9);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
        }}
        
        .progress-fill.high {{
            background: linear-gradient(90deg, #27ae60, #229954);
        }}
        
        .progress-fill.medium {{
            background: linear-gradient(90deg, #f39c12, #d68910);
        }}
        
        .progress-fill.low {{
            background: linear-gradient(90deg, #e74c3c, #c0392b);
        }}
        
        .trend-indicator {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }}
        
        .trend-indicator.improving {{
            background: #d5f4e6;
            color: #27ae60;
        }}
        
        .trend-indicator.stable {{
            background: #fef5e7;
            color: #f39c12;
        }}
        
        .trend-indicator.declining {{
            background: #fadbd8;
            color: #e74c3c;
        }}
        
        .no-data {{
            text-align: center;
            color: #95a5a6;
            padding: 40px;
            font-style: italic;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #95a5a6;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 AI Alert Management - Performance Dashboard</h1>
        <div class="date-range">
            Reporting Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
        </div>
        
        <h2>📊 System Overview</h2>
        <div class="summary-grid">
            <div class="metric-card success">
                <div class="metric-label">Total Feedback</div>
                <div class="metric-value">{system_metrics.total_feedback_count}</div>
                <div class="metric-subtitle">Incidents evaluated</div>
            </div>
            
            <div class="metric-card {'success' if system_metrics.average_overall_quality >= 4 else 'warning' if system_metrics.average_overall_quality >= 3 else 'danger'}">
                <div class="metric-label">Average Quality</div>
                <div class="metric-value">{system_metrics.average_overall_quality:.1f}/5</div>
                <div class="metric-subtitle">
                    <span class="trend-indicator {system_metrics.quality_trend_direction}">
                        {system_metrics.quality_trend_direction.upper()}
                    </span>
                </div>
            </div>
            
            <div class="metric-card success">
                <div class="metric-label">Time Saved</div>
                <div class="metric-value">{system_metrics.total_time_saved_minutes}</div>
                <div class="metric-subtitle">minutes total (avg: {system_metrics.average_time_saved_minutes:.0f} min)</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Feedback Coverage</div>
                <div class="metric-value">{sum(system_metrics.feedback_rate_by_stage.values())}</div>
                <div class="metric-subtitle">across all stages</div>
            </div>
        </div>
        
        {'<h2>📋 Stage 2: Classification</h2>' + self._render_stage2_metrics(stage2_metrics) if stage2_metrics else ''}
        
        {'<h2>🔗 Stage 3: Correlation</h2>' + self._render_stage3_metrics(stage3_metrics) if stage3_metrics else ''}
        
        {'<h2>🔍 Stage 4: Root Cause Analysis</h2>' + self._render_stage4_metrics(stage4_metrics) if stage4_metrics else ''}
        
        <div class="footer">
            Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AI Alert Management System v1.0
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _render_stage2_metrics(self, metrics: Stage2Metrics) -> str:
        """Render Stage 2 metrics section."""
        return f"""
        <div class="stage-section">
            <div class="summary-grid">
                <div class="metric-card">
                    <div class="metric-label">Overall Accuracy</div>
                    <div class="metric-value">{metrics.overall_accuracy:.1%}</div>
                    <div class="progress-bar">
                        <div class="progress-fill {'high' if metrics.overall_accuracy >= 0.8 else 'medium' if metrics.overall_accuracy >= 0.6 else 'low'}" 
                             style="width: {metrics.overall_accuracy * 100}%">
                            {metrics.overall_accuracy:.1%}
                        </div>
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Usefulness</div>
                    <div class="metric-value">{metrics.average_usefulness:.1f}/5</div>
                    <div class="metric-subtitle">{metrics.total_feedback_count} evaluations</div>
                </div>
            </div>
            
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Classification Field</th>
                        <th>Accuracy</th>
                        <th>Visual</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Alert Type</td>
                        <td>{metrics.alert_type_accuracy:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.alert_type_accuracy >= 0.8 else 'medium' if metrics.alert_type_accuracy >= 0.6 else 'low'}" 
                                     style="width: {metrics.alert_type_accuracy * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Severity</td>
                        <td>{metrics.severity_accuracy:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.severity_accuracy >= 0.8 else 'medium' if metrics.severity_accuracy >= 0.6 else 'low'}" 
                                     style="width: {metrics.severity_accuracy * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Business Impact</td>
                        <td>{metrics.business_impact_accuracy:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.business_impact_accuracy >= 0.8 else 'medium' if metrics.business_impact_accuracy >= 0.6 else 'low'}" 
                                     style="width: {metrics.business_impact_accuracy * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Priority</td>
                        <td>{metrics.priority_accuracy:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.priority_accuracy >= 0.8 else 'medium' if metrics.priority_accuracy >= 0.6 else 'low'}" 
                                     style="width: {metrics.priority_accuracy * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Routing</td>
                        <td>{metrics.routing_accuracy:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.routing_accuracy >= 0.8 else 'medium' if metrics.routing_accuracy >= 0.6 else 'low'}" 
                                     style="width: {metrics.routing_accuracy * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
            
            <p style="margin-top: 15px; color: #7f8c8d; font-size: 14px;">
                💡 Most corrected field: <strong>{metrics.most_corrected_field}</strong> ({metrics.correction_count} corrections)
            </p>
        </div>
        """
    
    def _render_stage3_metrics(self, metrics: Stage3Metrics) -> str:
        """Render Stage 3 metrics section."""
        return f"""
        <div class="stage-section">
            <div class="summary-grid">
                <div class="metric-card">
                    <div class="metric-label">Grouping Accuracy</div>
                    <div class="metric-value">{metrics.grouping_accuracy:.1%}</div>
                    <div class="progress-bar">
                        <div class="progress-fill {'high' if metrics.grouping_accuracy >= 0.8 else 'medium' if metrics.grouping_accuracy >= 0.6 else 'low'}" 
                             style="width: {metrics.grouping_accuracy * 100}%">
                            {metrics.grouping_accuracy:.1%}
                        </div>
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Usefulness</div>
                    <div class="metric-value">{metrics.average_usefulness:.1f}/5</div>
                    <div class="metric-subtitle">{metrics.total_feedback_count} evaluations</div>
                </div>
            </div>
            
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>False Positive Rate</td>
                        <td>{metrics.false_positive_rate:.1%}</td>
                        <td>Alerts grouped together that should be separate</td>
                    </tr>
                    <tr>
                        <td>False Negative Rate</td>
                        <td>{metrics.false_negative_rate:.1%}</td>
                        <td>Alerts that should have been included but weren't</td>
                    </tr>
                    <tr>
                        <td>Avg Alerts per Incident</td>
                        <td>{metrics.average_alerts_per_incident:.1f}</td>
                        <td>Average number of alerts grouped per incident</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """
    
    def _render_stage4_metrics(self, metrics: Stage4Metrics) -> str:
        """Render Stage 4 metrics section."""
        missing_evidence_note = f"<br>💡 Most missing: <strong>{metrics.most_missing_evidence_type}</strong>" if metrics.most_missing_evidence_type else ""
        
        return f"""
        <div class="stage-section">
            <div class="summary-grid">
                <div class="metric-card">
                    <div class="metric-label">RCA Correctness</div>
                    <div class="metric-value">{metrics.rca_correctness_rate:.1%}</div>
                    <div class="progress-bar">
                        <div class="progress-fill {'high' if metrics.rca_correctness_rate >= 0.8 else 'medium' if metrics.rca_correctness_rate >= 0.6 else 'low'}" 
                             style="width: {metrics.rca_correctness_rate * 100}%">
                            {metrics.rca_correctness_rate:.1%}
                        </div>
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">RCA Helpfulness</div>
                    <div class="metric-value">{metrics.rca_helpfulness_rate:.1%}</div>
                    <div class="metric-subtitle">{metrics.total_feedback_count} evaluations</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Usefulness</div>
                    <div class="metric-value">{metrics.average_rca_usefulness:.1f}/5</div>
                    <div class="metric-subtitle">Overall RCA rating</div>
                </div>
            </div>
            
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Aspect</th>
                        <th>Rate/Score</th>
                        <th>Visual</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Evidence Sufficiency</td>
                        <td>{metrics.evidence_sufficiency_rate:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.evidence_sufficiency_rate >= 0.8 else 'medium' if metrics.evidence_sufficiency_rate >= 0.6 else 'low'}" 
                                     style="width: {metrics.evidence_sufficiency_rate * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Evidence Relevance</td>
                        <td>{metrics.evidence_relevance_rate:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.evidence_relevance_rate >= 0.8 else 'medium' if metrics.evidence_relevance_rate >= 0.6 else 'low'}" 
                                     style="width: {metrics.evidence_relevance_rate * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Recommendations Helpful</td>
                        <td>{metrics.recommendations_helpful_rate:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.recommendations_helpful_rate >= 0.8 else 'medium' if metrics.recommendations_helpful_rate >= 0.6 else 'low'}" 
                                     style="width: {metrics.recommendations_helpful_rate * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Recommendations Actionable</td>
                        <td>{metrics.recommendations_actionable_rate:.1%}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.recommendations_actionable_rate >= 0.8 else 'medium' if metrics.recommendations_actionable_rate >= 0.6 else 'low'}" 
                                     style="width: {metrics.recommendations_actionable_rate * 100}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Support Communication</td>
                        <td>{metrics.average_support_communication_quality:.1f}/5</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.average_support_communication_quality >= 4 else 'medium' if metrics.average_support_communication_quality >= 3 else 'low'}" 
                                     style="width: {metrics.average_support_communication_quality * 20}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Stakeholder Communication</td>
                        <td>{metrics.average_stakeholder_communication_quality:.1f}/5</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'high' if metrics.average_stakeholder_communication_quality >= 4 else 'medium' if metrics.average_stakeholder_communication_quality >= 3 else 'low'}" 
                                     style="width: {metrics.average_stakeholder_communication_quality * 20}%"></div>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
            
            <p style="margin-top: 15px; color: #7f8c8d; font-size: 14px;">
                {missing_evidence_note}
            </p>
        </div>
        """
