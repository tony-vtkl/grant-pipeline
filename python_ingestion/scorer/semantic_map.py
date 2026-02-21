"""Semantic mapping configuration for domain terminology.

Maps grant opportunity language to VTKL capabilities.
"""

from typing import List, Dict

SEMANTIC_MAPPINGS: Dict[str, List[str]] = {
    # Cyberinfrastructure & Data
    "cyberinfrastructure": [
        "data governance",
        "secure data pipelines",
        "infrastructure automation",
        "data architecture",
        "data platforms"
    ],
    "data management": [
        "data governance",
        "ETL pipelines",
        "data quality",
        "data integration",
        "data warehousing",
        "data lakes"
    ],
    "data science": [
        "machine learning",
        "predictive analytics",
        "statistical modeling",
        "data analysis",
        "business intelligence"
    ],
    
    # Decision Support & AI
    "decision support": [
        "AI workflows",
        "machine learning models",
        "predictive analytics",
        "business intelligence",
        "analytics dashboards",
        "decision automation"
    ],
    "artificial intelligence": [
        "machine learning",
        "neural networks",
        "deep learning",
        "LLM integration",
        "natural language processing",
        "computer vision"
    ],
    "AI/ML": [
        "machine learning",
        "neural networks",
        "LLM integration",
        "model training",
        "model deployment",
        "MLOps"
    ],
    
    # Automation & Workflows
    "automation": [
        "agent configuration",
        "workflow orchestration",
        "DevOps",
        "CI/CD",
        "infrastructure as code",
        "process automation"
    ],
    "workflow automation": [
        "workflow orchestration",
        "agent configuration",
        "task automation",
        "process optimization"
    ],
    
    # Cloud & Infrastructure
    "cloud computing": [
        "AWS",
        "Azure",
        "GCP",
        "cloud-native",
        "serverless",
        "cloud migration",
        "multi-cloud"
    ],
    "cloud infrastructure": [
        "cloud architecture",
        "infrastructure as code",
        "container orchestration",
        "Kubernetes",
        "Docker"
    ],
    
    # Software Development
    "software development": [
        "application development",
        "API development",
        "microservices",
        "full-stack development",
        "agile development"
    ],
    "software engineering": [
        "software architecture",
        "system design",
        "technical architecture",
        "software integration"
    ],
    
    # Security & Compliance
    "cybersecurity": [
        "security architecture",
        "threat detection",
        "security monitoring",
        "compliance automation",
        "security operations"
    ],
    "information security": [
        "data security",
        "access control",
        "encryption",
        "security compliance",
        "risk management"
    ],
    
    # Research & Development
    "research and development": [
        "R&D",
        "innovation",
        "proof of concept",
        "prototyping",
        "experimental development"
    ],
    "innovation": [
        "emerging technologies",
        "cutting-edge solutions",
        "novel approaches",
        "technology advancement"
    ],
    
    # Government & Federal
    "federal IT": [
        "government technology",
        "federal systems",
        "federal modernization",
        "government cloud"
    ],
    "digital transformation": [
        "modernization",
        "digital services",
        "legacy system migration",
        "technology transformation"
    ],
    
    # Consulting & Professional Services
    "IT consulting": [
        "technical consulting",
        "technology advisory",
        "systems integration",
        "IT strategy"
    ],
    "professional services": [
        "consulting services",
        "advisory services",
        "technical services",
        "managed services"
    ]
}


def find_semantic_matches(text: str) -> List[tuple]:
    """Find semantic matches between opportunity text and VTKL capabilities.
    
    Args:
        text: Opportunity description or raw text
        
    Returns:
        List of (category, matched_capability, context) tuples
    """
    
    if not text:
        return []
    
    text_lower = text.lower()
    matches = []
    
    for category, capabilities in SEMANTIC_MAPPINGS.items():
        # Check if category keyword appears in text
        if category.lower() in text_lower:
            # Find which specific capabilities match
            for capability in capabilities:
                if capability.lower() in text_lower:
                    # Extract context (sentence containing the match)
                    context = _extract_context(text, capability)
                    matches.append((category, capability, context))
        else:
            # Check each capability directly
            for capability in capabilities:
                if capability.lower() in text_lower:
                    context = _extract_context(text, capability)
                    matches.append((category, capability, context))
    
    return matches


def _extract_context(text: str, keyword: str, window: int = 100) -> str:
    """Extract context around a keyword match.
    
    Args:
        text: Full text
        keyword: Keyword to find
        window: Characters before/after to include
        
    Returns:
        Context string
    """
    
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    idx = text_lower.find(keyword_lower)
    if idx == -1:
        return ""
    
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    
    context = text[start:end].strip()
    
    # Add ellipsis if truncated
    if start > 0:
        context = "..." + context
    if end < len(text):
        context = context + "..."
    
    return context


def get_vtkl_focus_areas() -> List[str]:
    """Get VTKL's primary focus areas for mission fit scoring.
    
    Returns:
        List of VTKL core capabilities
    """
    
    return [
        "AI workflows",
        "data governance",
        "agent configuration",
        "decision support systems",
        "workflow automation",
        "machine learning operations",
        "data pipeline development",
        "cloud-native architecture",
        "API development",
        "DevOps automation"
    ]
