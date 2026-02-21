"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_grants_gov_response():
    """Sample Grants.gov API response."""
    return {
        "hitCount": 2,
        "oppHits": [
            {
                "id": "335512",
                "number": "HHS-2024-ACF-OCS-TE-0001",
                "title": "Community Services Block Grant",
                "agencyName": "Department of Health and Human Services",
                "openDate": "01/15/2024",
                "closeDate": "03/18/2024",
                "synopsis": "CSBG competitive grant program",
                "awardCeiling": 500000,
                "awardFloor": 100000,
            },
            {
                "id": "335513",
                "number": "NSF-25-001",
                "title": "CSSI: Cyberinfrastructure for Sustained Scientific Innovation",
                "agencyName": "National Science Foundation",
                "openDate": "02/01/2024",
                "closeDate": "04/30/2024",
                "synopsis": "NSF cyberinfrastructure research and development",
            }
        ]
    }


@pytest.fixture
def sample_sam_gov_response():
    """Sample SAM.gov API response."""
    return {
        "totalRecords": 1,
        "opportunitiesData": [
            {
                "noticeId": "abc123",
                "solicitationNumber": "W911NF-24-R-0001",
                "title": "Army Research Laboratory AI/ML Research",
                "organizationName": "Army Research Laboratory",
                "fullParentPathName": "DEPT OF DEFENSE > DEPT OF THE ARMY > ARMY RESEARCH LAB",
                "postedDate": "01/15/2024",
                "responseDeadLine": "03/18/2024",
                "naicsCode": ["541511", "541512", "541715"],
                "typeOfSetAsideDescription": "Total Small Business Set-Aside",
                "type": "Solicitation",
                "description": "Seeking AI and machine learning research partners for defense applications",
            }
        ]
    }


@pytest.fixture
def sample_sbir_gov_response():
    """Sample SBIR.gov API response."""
    return [
        {
            "solicitation_number": "N241-001",
            "solicitation_id": "12345",
            "topic_title": "Artificial Intelligence for Naval Systems",
            "agency": "Navy",
            "agency_name": "Department of the Navy",
            "open_date": "2024-01-15",
            "close_date": "2024-03-18",
            "description": "Phase II SBIR for AI development in naval combat systems",
            "award_amount_max": 1500000,
            "naics": "541511,541512",
            "solicitation_url": "https://www.sbir.gov/sbirsearch/detail/12345",
        }
    ]
