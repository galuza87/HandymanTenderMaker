# --- RAG Database & Guidelines (Construction + Handyman) ---
AVAILABLE_TASKS = {
    "quote_request": {
        "name": "Construction Quote Request",
        "description": "Builds a precise quote request to send to subcontractors or material suppliers.",
        "required_fields": ["project_type", "materials_or_scope", "deadline"],
        "gold_standard": "You are a professional Construction Project Manager. Please draft a formal Quote Request for the following project:\n\n- **Project Type**: {project_type}\n- **Materials / Scope of Work**: {materials_or_scope}\n- **Required Delivery/Completion Deadline**: {deadline}\n\nPlease generate a highly detailed and professional request that I can send directly to subcontractors, prompting them to bid with their best pricing, timeline, and breakdown of labor/material costs."
    },
    "tender_request": {
        "name": "Subcontractor Tender Request",
        "description": "Drafts a detailed Tender request detailing the current state and desired results.",
        "required_fields": ["current_state", "desired_result", "technical_requirements"],
        "gold_standard": "You are an expert Head Contractor. Please draft a subcontractor tender document. \n\n- **Current State of Project**: {current_state}\n- **Desired Result**: {desired_result}\n- **Technical & Safety Requirements**: {technical_requirements}\n\nFormat this into a professional bidding document specifying compliance terms, milestone requirements, and an invitation to submit proposals."
    },
    "handyman_request": {
        "name": "Handyman Service Request",
        "description": "Drafts a detailed service request for handyman tasks such as plumbing, electrical work, appliance fixing, and carpentry.",
        "required_fields": ["major_category", "sub_category", "job_description", "timeframe"],
        "gold_standard": "You are a professional Handyman Coordinator. Please draft a formal service request for the following handyman job:\n\n- **Service Category**: {major_category} ({sub_category})\n- **Detailed Job Description**: {job_description}\n- **Desired Timeframe**: {timeframe}\n\nPlease generate a clear and professional work order so that contractors can bid on this job with their pricing and availability."
    }
}