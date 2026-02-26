# Team Missions & Quick Reference

## Your Team's Mission

### Weight Team

You're building: The industrial weighing system that tracks trucks and calculates fruit weights.

**Core responsibilities:**

Record truck weighings when entering and exiting the factory
Manage container weight data (uploaded from files)
Generate weight reports by time period
Provide APIs for Billing team to retrieve weight data

**Critical success factor**: Your APIs must be reliable - Billing team depends on them!

### Billing Team

You're building: The payment system that generates invoices for fruit producers.

**Core responsibilities:**

Manage producers and their registered trucks
Upload and manage pricing rates
Generate accurate invoices using Weight data
Track payment history

**You depend on Weight team for delivery data. Coordinate early and often.**

## DevOps Team

You're building: The CI/CD pipeline and infrastructure that enables safe, automated deployments.

**Core responsibilities:**

Set up GitHub repository with proper branching strategy
Build automated CI/CD pipeline
Manage test and production environments
Set up monitoring and notifications
Support development teams (your #1 priority!)

**Critical success factor:** Development teams succeed = You succeed. 

## Weekly Timeline

### Day 1: Foundation

Goal: VCS, CI server, `/health` for all services

#### DevOps Team

✅ Open shared GitHub project
✅ Collect mail addresses from all team members
✅ Basic CI: build + deploy (keep it simple!)


### Billing Team

✅ `GET /health`
✅ `POST /provider`
✅ `PUT /provider/<id>`


### Weight Team

✅ `GET /health`
✅ `POST /weight`
✅ `GET /weight`


### Day 2: Core Development

Goal: Weight APIs complete, Billing domain management


#### DevOps Team

✅ Test environment setup
✅ Mailing system
🎯 BONUS: Monitor


#### Billing Team

✅ POST /truck
✅ PUT /truck/<id>
✅ GET /truck/<id>
✅ POST /rates
✅ GET /rates


#### Weight Team

✅ GET /item
✅ GET /session
✅ POST /batch-weight

Note: By end of Day 2, Weight team should have ALL their APIs done except GET /unknown. Billing should start planning GET /bill integration.


### Day 3: Integration & Testing

Goal: Full E2E + Basic Sanity


#### DevOps Team

✅ Manage testing for dev teams
✅ End-to-end test automation
🎯 BONUS: Rollback functionality


#### Billing Team

✅ GET /bill (THE BIG ONE - integrate with Weight!)
✅ E2E tests
🎯 BONUS: UI


#### Weight Team

✅ GET /unknown
✅ E2E tests
🎯 BONUS: UI

This is integration day: Billing and Weight must work together successfully by end of day!

### Day 4: Full Functionality

Goal: Everything must work end-to-end

#### DevOps Team

✅ Fully working CI + mailing system
✅ All environments stable

#### Billing Team

✅ GET /bill working (last chance if not done!)
✅ All tests passing

#### Weight Team

✅ Full integration with Billing verified
✅ All APIs stable and tested

By end of Day 4: Complete system should be operational and ready for demo.

### Day 5: Demo Day!

Goal: Present your work!

### All Teams

✅ Should all work on presentations!
✅ Last touches and polish
✅ Last bug fixes
✅ Demo preparation (screenshots, backup plans)
✅ Team presentations

Team leaders: Focus on presentation preparation. Make sure everyone knows their part!