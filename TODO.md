# TODO - IBKR MF Syncer

## Completed Items ✅

### Environment Variable Support
- [x] **Environment variable configuration with config.ini fallback** (Completed: Jan 2026)
  - ✅ Implemented `get_config_value()` function in main.py
  - ✅ Support for: MF_EMAIL, MF_PASSWORD, MF_IB_INSTITUTION_URL, IBKR_FLEX_TOKEN, IBKR_FLEX_QUERY_ID
  - ✅ Created .env.template for easy local setup
  - ✅ Updated .gitignore to exclude .env files
  - ✅ Updated documentation (README.md, CLAUDE.md)
  - ✅ Streamlit app pre-populates from environment variables
  - ✅ Lambda-ready configuration management

### Package Management
- [x] **Update and pin package versions** (Completed: Jan 2026)
  - ✅ Pinned minimum versions for all dependencies
  - ✅ Added version constraints (pandas <3.0.0 for stability)
  - ✅ Added package purpose documentation in requirements.txt
  - ✅ Latest versions: streamlit ≥1.52.0, playwright ≥1.57.0, beautifulsoup4 ≥4.14.0, yfinance ≥1.0.0, pandas ≥2.2.0

### Documentation
- [x] **Create TODO.md** (Completed: Jan 2026)
- [x] **Create CLAUDE.md** (Completed: Jan 2026)
- [x] **Add inline TODO comments throughout codebase** (Completed: Jan 2026)

## Security & Authentication (HIGH PRIORITY)

### Target Deployment: AWS Lambda (Automated Scheduling)

**Current Status**: ✅ Environment variable support implemented (suitable for Lambda)
**Next Step**: Choose credential management approach for Lambda deployment

### Option 1: Environment Variables (CURRENT - Simple & Cost-Effective) ⭐
- [x] **Basic implementation complete**
  - ✅ Works locally and in Lambda
  - ✅ No additional AWS services required
  - ✅ Set directly in Lambda configuration
  - ⚠️ Credentials visible in Lambda console to authorized users
  - ✅ Suitable for personal/small-scale use

- [ ] **Optional: Add AWS Secrets Manager integration**
  - Only if higher security needed
  - Adds cost (~$0.40/month per secret)
  - Better audit trail with CloudTrail
  - Use for production/shared environments

### Option 2: MoneyForward Official API with OAuth 2.0 (IDEAL LONG-TERM)
- [ ] **Contact MoneyForward for API Partnership**
  - **MoneyForward API Status**: Official API exists but currently closed to partner companies only
  - **API Documentation**: https://github.com/moneyforward/api-doc
  - **Benefits for Lambda**:
    - ✅ No browser automation (eliminates 50-100MB Chromium layer)
    - ✅ Faster execution (API calls vs browser automation)
    - ✅ Lower cost (128MB memory vs 1GB for Playwright)
    - ✅ More reliable (no UI breakage)
    - ✅ OAuth token refresh (better security)
  - **Challenges**:
    - API currently closed/partner-only
    - No public application process documented
    - May require business partnership agreement
    - Need to verify manual asset management via API

- [ ] **If API access granted - Implementation tasks**:
  1. Implement OAuth 2.0 Authorization Code Flow
  2. Store refresh tokens in environment variables or Secrets Manager
  3. Replace Playwright automation with API calls (`/api/v1/user_assets`, `/api/v1/accounts`)
  4. Implement token refresh logic
  5. Remove Playwright dependency (significant package size reduction)

### Deployment Approaches Comparison

| Approach | Cost | Security | Complexity | Lambda Package Size | Recommended For |
|----------|------|----------|------------|---------------------|-----------------|
| **Env Vars (Current)** | Free | Medium | Low | ~100MB (Playwright) | Personal use, MVP |
| **Env Vars + Secrets Mgr** | ~$0.40/mo | High | Medium | ~100MB (Playwright) | Shared/Production |
| **MoneyForward API** | Free | High | Medium | ~10MB (no browser) | All scenarios (ideal) |

### Decision Made:
✅ **Use Environment Variables for initial Lambda deployment** (simple, free, adequate security for personal use)
📋 **Future**: Migrate to MoneyForward API if/when access becomes available

## Asset Type Support

### Currently Supported
- [x] **STK** - Physical Stocks
- [x] **OPT** - Options

### Not Yet Supported (Priority Order)

#### High Priority
- [ ] **FUT** - Futures
  - Research MoneyForward asset type mapping for futures
  - Implement futures-specific data extraction from IBKR Flex Query
  - Add FUT to supported asset categories in `ibkr_flex_query_client.py`
  - Implement MoneyForward sync logic for futures positions

- [ ] **BND** - Bonds
  - Research MoneyForward asset type mapping for bonds
  - Handle bond-specific attributes (coupon rate, maturity date, etc.)
  - Add BND to supported asset categories
  - Implement MoneyForward sync logic for bond positions

#### Medium Priority
- [ ] **FND** - Mutual Funds / Investment Trusts
  - Research MoneyForward asset type mapping for mutual funds
  - Handle fund-specific attributes (NAV, distribution, etc.)
  - Add FND to supported asset categories
  - Implement MoneyForward sync logic for fund positions

- [ ] **WAR** - Warrants
  - Research MoneyForward asset type mapping for warrants
  - Handle warrant-specific attributes (exercise price, expiry, etc.)
  - Add WAR to supported asset categories
  - Implement MoneyForward sync logic for warrant positions

#### Low Priority
- [ ] **CFD** - Contracts for Difference
  - Research MoneyForward asset type mapping for CFDs
  - Handle CFD-specific attributes (margin requirements, etc.)
  - Add CFD to supported asset categories
  - Implement MoneyForward sync logic for CFD positions

- [ ] **SWP** - Forex / Swaps
  - Research MoneyForward asset type mapping for forex positions
  - Handle forex-specific attributes (lot size, pip value, etc.)
  - Add SWP to supported asset categories
  - Implement MoneyForward sync logic for forex positions

- [ ] **ICS** - Inter-Commodity Spreads
  - Research MoneyForward asset type mapping for spreads
  - Handle spread-specific attributes
  - Add ICS to supported asset categories
  - Implement MoneyForward sync logic for spread positions

## AWS Lambda Deployment (NEXT PRIORITY)

### Lambda Function Setup
- [ ] **Create Lambda handler function**
  - Create `lambda_handler.py` as entry point
  - Import and call main() from main.py
  - Handle Lambda event/context parameters
  - Return structured response (success/failure, summary)

- [ ] **Package for Lambda deployment**
  - Create deployment package with dependencies
  - Use Docker for consistent build environment
  - Consider using AWS SAM or Serverless Framework
  - Or use Lambda Layers for large dependencies (Playwright)

- [ ] **Playwright Lambda compatibility**
  - Use `playwright-aws-lambda` or similar package
  - Configure for headless Chromium in Lambda environment
  - Set up Lambda with sufficient memory (1GB minimum)
  - Configure timeout (5-10 minutes)

### EventBridge Scheduling
- [ ] **Set up automated triggers**
  - Create EventBridge (CloudWatch Events) rule
  - Schedule: Daily at specific time (e.g., 2 AM JST)
  - Or: Weekly on specific day
  - Configure retry logic for failures

### Monitoring & Logging
- [ ] **Add CloudWatch logging**
  - Structured logging with timestamps
  - Log sync summary (assets added/modified/deleted)
  - Error tracking and alerting
  - Dashboard for monitoring execution history

- [ ] **Optional: SNS notifications**
  - Email notification on sync completion
  - Alert on failures
  - Summary of changes made

### Cost Optimization
- [ ] **Optimize Lambda configuration**
  - Right-size memory allocation
  - Minimize cold start time
  - Use ARM64 (Graviton2) if compatible
  - Monitor and optimize execution time

## Technical Improvements

### Exchange Rate Accuracy
- [ ] **Improve currency conversion accuracy**
  - Current implementation uses Yahoo Finance (approximate)
  - Consider alternative FX data sources (OANDA, XE, ECB)
  - Add caching to reduce API calls during single run
  - Handle FX rate fetch failures gracefully (retry, fallback)
  - Add logging for FX rate usage

### IBKR Token Management
- [ ] **Add token expiration warning system**
  - IBKR Flex Token expires after 1 year
  - Store token creation date in config/environment
  - Calculate days until expiration
  - Warning notification at 30/14/7 days before expiration
  - Document token renewal process in README

### Error Handling & Reliability
- [ ] **Improve error handling and logging**
  - Add structured logging (use Python logging module)
  - Better error messages for common failures
  - Implement retry logic for network operations
  - Handle MoneyForward UI changes gracefully
  - Add dry-run mode for testing without making changes

- [ ] **Handle edge cases**
  - Empty position handling improvements
  - Dialog handling race condition (main.py:50-54)
  - User agent string updates if MoneyForward changes requirements
  - Handle session timeouts

### Testing
- [ ] **Add unit tests for core functionality**
  - Test IBKR Flex Query parsing (ibkr_flex_query_client.py)
  - Test currency conversion logic (utils.py)
  - Test MoneyForward data reconciliation (moneyforward_processing.py)
  - Mock Playwright interactions for testing
  - Use pytest framework

- [ ] **Add integration tests**
  - Test end-to-end workflow with test data
  - Test error scenarios and edge cases
  - Mock external services (IBKR API, MoneyForward)

### Code Quality
- [ ] **Add type hints**
  - Add type annotations to all functions
  - Use mypy for static type checking
  - Improve IDE autocomplete and documentation

- [ ] **Add docstrings**
  - Document all public functions
  - Include parameter descriptions and return types
  - Add usage examples in docstrings

### Documentation
- [ ] **Improve user documentation**
  - Add troubleshooting guide
  - Document MoneyForward asset type mappings
  - Add screenshots for setup process
  - Create FAQ section
  - Add Lambda deployment guide

## Future Enhancements (Lower Priority)

### Multi-Account Support
- [ ] **Support multiple IBKR accounts**
  - Handle multiple query IDs in configuration
  - Separate MoneyForward institutions per account
  - Aggregate reporting across accounts
  - Command-line argument to select account

### Performance Optimization
- [ ] **Optimize execution performance**
  - Parallel processing for multiple assets
  - Reduce browser automation overhead
  - Batch MoneyForward updates where possible
  - Investigate MoneyForward bulk update APIs

### Enhanced Reporting
- [ ] **Add reporting capabilities**
  - Generate summary report after each sync
  - Track changes over time (history database)
  - Compare positions day-over-day
  - Export sync logs to CSV/JSON

### User Experience
- [ ] **Improve CLI experience**
  - Add command-line arguments (--dry-run, --verbose, --account)
  - Interactive setup wizard for first-time users
  - Better progress indicators during sync
  - Color-coded console output

## Development Workflow

### Branch Strategy
- Use feature branches for all new development
- Branch naming: `feat/`, `fix/`, `docs/`, `chore/`
- Merge to `main` only after testing
- Create commits throughout development for checkpoints

### Commit Message Format
- feat: New features
- fix: Bug fixes
- docs: Documentation changes
- style: Formatting, missing semi colons, etc.
- refactor: Code refactoring
- test: Adding tests
- chore: Maintenance tasks

## Known Issues & Limitations

### Active Issues
- [ ] Dialog handling race condition (partially mitigated in main.py:50-54)
- [ ] User agent string may need updates if MoneyForward changes requirements
- [ ] Empty position handling edge cases
- [ ] ibflex package hasn't been updated in 4+ years (still functional)

### Constraints
- Only supports Cash, Stocks (STK), and Options (OPT)
- Yahoo Finance FX rates are approximate
- IBKR Flex Token expires after 1 year (manual renewal required)
- MoneyForward requires browser automation (no public API access)
- Asset name limited to 20 characters in MoneyForward
- Asset value limited to 12 characters in MoneyForward

## Resources

### Documentation
- IBKR Flex Web Service: https://www.interactivebrokers.com/campus/ibkr-api-page/flex-web-service/
- MoneyForward API (closed): https://github.com/moneyforward/api-doc
- Playwright Python: https://playwright.dev/python/

### Related Projects
- ibflex library: https://pypi.org/project/ibflex/
- Playwright AWS Lambda: https://github.com/JupiterOne/playwright-aws-lambda
