
**Enterprise Chat: MVT → MVP Transition Requirements**  
  
**Purpose**  
  
This document defines the high-level functional and architectural requirements for advancing the Enterprise Chat Messaging Platform (ECMP) from the Minimum Viable Test (MVT) implementation to the Minimum Viable Product (MVP) release. It covers the transition from a single-tenant, single-channel pilot to a scalable, compliant, multi-tenant enterprise platform.  
  
-----  
  
**1. Conversation Model Expansion**  
  
- Expand conversation ownership beyond GxP to support multiple tenants and channels under a unified model  
- Each conversation must represent a single, continuous interaction between Marriott and a guest, regardless of the originating system or channel  
- Allow external systems (e.g., GxP, CEC, Loyalty) to link their own case identifiers to ECMP conversations  
- Enable conversation continuity across stays or business units while preserving tenant isolation  
  
-----  
  
**2. Routing Service**  
  
- Introduce a centralized routing layer that determines which provider, sender identity, or telecom account to use for each outbound message  
- Routing decisions must be configurable by tenant, brand, property, or region without code changes  
- Support failover or reroute logic when a provider or sender pool is unavailable  
- Routing must log and expose the selected path for audit and troubleshooting  
  
-----  
  
**3. Consent and Compliance**  
  
- Implement platform-level enforcement of guest consent before any outbound communication  
- Support compliance handling for STOP, HELP, and similar keywords  
- Maintain a complete audit trail of consent events (opt-in, opt-out, reinstatement)  
- Integrate consent state checks directly into outbound send logic to prevent accidental violations  
  
-----  
  
**4. Template Management**  
  
- Add a centralized template library with versioning, approval workflows, and publishing controls  
- Templates must support dynamic variables and allow variations by:  
 - Locale (e.g., English, Spanish)  
 - Brand or property  
 - Channel (SMS, WhatsApp, etc.)  
 - Program or customer segment (e.g., Bonvoy member vs. non-member)  
- The system must automatically select the correct template variant based on contextual attributes such as membership, brand, or message type  
- Templates must undergo governance approval before activation  
  
-----  
  
**5. Delivery Receipts (DLRs)**  
  
- Capture and normalize delivery receipt events from external providers  
- Standardize states across all channels (e.g., sent, delivered, failed)  
- Link DLRs to the corresponding message and evidence chain for full lifecycle traceability  
- Use DLR data to drive reliability metrics and delivery dashboards  
  
-----  
  
**6. Outbound Adapter Layer**  
  
- Introduce a formal outbound adapter for systems like GxP, CEC, or future CRMs  
- Adapters handle all outbound posting, authentication, retry, and error management responsibilities  
- Bridge and Send Worker communicate with adapters only — no direct CRM posting  
- Each adapter follows a consistent contract, ensuring future extensibility across systems  
  
-----  
  
**7. Scalability and Performance**  
  
- Define target throughput and latency objectives at the tenant and channel level  
- The platform must scale horizontally to meet enterprise traffic requirements during peak events  
- Implement autoscaling and queue-based flow control to maintain service stability under load  
- Establish operational performance baselines (e.g., 10,000+ messages per minute per tenant)  
  
-----  
  
**8. Observability and Monitoring**  
  
- Provide unified dashboards showing message throughput, error rates, provider performance, and consent activity  
- Introduce proactive alerting tied to service-level objectives (SLOs)  
- Include traceability across the full message lifecycle — from scheduling to guest receipt  
- Logging and metrics must include standardized identifiers (tenant, channel, conversation, correlation)  
  
-----  
  
**9. Security and Privacy**  
  
- Enforce per-tenant isolation for all data, credentials, and logs  
- Strengthen authentication and key management with Vault-based rotation policies  
- Ensure least-privilege access to audit records and configuration data  
- Align data handling with Marriott’s privacy and regulatory compliance frameworks (e.g., TCPA, GDPR)  
  
-----  
  
**10. Future-Ready Channel Framework**  
  
- Design a channel-agnostic architecture allowing new channels (e.g., WhatsApp, Email, Web Chat) to be added with minimal code changes  
- Standardize the interface pattern for all channels: send, receive, evidence, and DLR  
- Keep new channels disabled in MVP but ensure readiness for phased enablement  
- Channel additions must not require schema changes or platform redeployments  
  
-----  
  
**11. Governance and Change Control**  
  
- Establish governance workflows for templates, routing policies, and consent rule changes  
- All new templates or channel activations must undergo business and legal approval  
- Introduce version control for configuration and infrastructure definitions  
- Maintain full traceability between operational actions and resulting message flows  
  
-----  
  
**Summary**  
  
The MVP evolution of ECMP transforms a single-use SMS proof-of-concept into a production-grade, multi-tenant, extensible messaging platform. It introduces consent enforcement, routing intelligence, template orchestration, observability, and security hardening — all while preserving the evidence-based architecture and stateless orchestration patterns established in MVT.