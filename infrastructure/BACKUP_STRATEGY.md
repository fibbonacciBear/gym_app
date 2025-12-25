# Database Backup Strategy

## Overview

Multi-tier backup strategy for RDS PostgreSQL with automated backups, point-in-time recovery, and long-term retention.

---

## Backup Tiers

### Tier 1: RDS Automated Backups (Built-in)

**What:** RDS takes automatic snapshots daily  
**Retention:** 30 days  
**Cost:** Free (included with RDS)  
**Recovery:** Point-in-time restore to any second within 30 days

```yaml
BackupRetentionPeriod: 30
PreferredBackupWindow: '03:00-04:00'  # 3 AM UTC (7 PM PST)
```

**Use case:** Quick recovery from accidental data deletion, database corruption

---

### Tier 2: AWS Backup Service (Enhanced)

#### Daily Backups
- **Schedule:** Every day at 3 AM UTC
- **Retention:** 30 days
- **Storage:** Standard (hot)
- **Cost:** ~$0.05/GB/month

#### Weekly Backups
- **Schedule:** Every Sunday at 4 AM UTC
- **Retention:** 90 days
- **Storage:** Moved to cold storage after 30 days
- **Cost:** ~$0.01/GB/month (cold storage)

#### Monthly Backups
- **Schedule:** 1st of each month at 5 AM UTC
- **Retention:** 365 days (1 year)
- **Storage:** Moved to cold storage after 60 days
- **Cost:** ~$0.01/GB/month (cold storage)

---

## Backup Architecture

```
┌─────────────────────────────────────────────────────┐
│ RDS PostgreSQL (Primary)                            │
│  └─ Automated snapshots (every day, 30-day PITR)   │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│ AWS Backup Vault (Encrypted with KMS)              │
│  ├─ Daily backups (30 days, standard storage)      │
│  ├─ Weekly backups (90 days, cold after 30)        │
│  └─ Monthly backups (365 days, cold after 60)      │
└─────────────────────────────────────────────────────┘
                     ↓
         (Optional: Cross-region copy)
┌─────────────────────────────────────────────────────┐
│ Backup Vault in us-east-1 (Disaster Recovery)      │
│  └─ Critical monthly backups replicated             │
└─────────────────────────────────────────────────────┘
```

---

## Recovery Scenarios

### Scenario 1: Accidental Table Drop (Last Hour)
**Use:** RDS Point-in-Time Restore

```bash
# Restore to 1 hour ago
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier prod-gym-app-db \
  --target-db-instance-identifier prod-gym-app-db-restored \
  --restore-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --region us-west-1

# Test the restored instance, then swap if good
```

**RTO:** ~15 minutes  
**RPO:** Seconds (point-in-time)

---

### Scenario 2: Database Corruption (Last Week)
**Use:** AWS Backup Daily Snapshot

```bash
# List recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name prod-gym-app-vault \
  --region us-west-1

# Restore from specific backup
aws backup start-restore-job \
  --recovery-point-arn <ARN from list> \
  --metadata file://restore-metadata.json \
  --iam-role-arn arn:aws:iam::ACCOUNT:role/AWSBackupRole \
  --region us-west-1
```

**RTO:** ~20 minutes  
**RPO:** 24 hours (daily backup)

---

### Scenario 3: Region Failure (Disaster Recovery)
**Use:** Cross-Region Backup Copy

**Setup:**
```bash
# Enable cross-region copy (add to CloudFormation or CLI)
aws backup update-backup-plan \
  --backup-plan-id <PLAN_ID> \
  --backup-plan file://cross-region-backup-plan.json
```

**RTO:** 1-2 hours (rebuild in new region)  
**RPO:** 24-48 hours (daily cross-region copy)

---

### Scenario 4: Ransomware / Malicious Deletion
**Use:** Monthly Backup (Long-term)

- Backups retained for 1 year
- Moved to cold storage (cheaper)
- Can restore to state from months ago

---

## Backup Costs (Estimated)

### Assumptions
- Database size: 5 GB (small, early stage)
- Daily backup delta: 500 MB
- Growth: 20% per month

### Monthly Costs

| Backup Type | Storage | Cost |
|-------------|---------|------|
| RDS Automated (30 days) | ~15 GB | **$0** (included) |
| AWS Backup Daily (30 days) | ~15 GB | ~$0.75 |
| AWS Backup Weekly (90 days, cold) | ~25 GB | ~$0.25 |
| AWS Backup Monthly (365 days, cold) | ~60 GB | ~$0.60 |
| **Total Backup Cost** | | **~$1.60/month** |

### At Scale (100 GB database)

| Backup Type | Storage | Cost |
|-------------|---------|------|
| RDS Automated | ~300 GB | $0 |
| AWS Backup (all tiers) | ~600 GB | ~$25/month |

---

## Backup Testing & Verification

### Monthly Backup Test (Recommended)

```bash
#!/bin/bash
# test-backup-restore.sh

# 1. Get latest backup
LATEST_BACKUP=$(aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name prod-gym-app-vault \
  --region us-west-1 \
  --query 'RecoveryPoints[0].RecoveryPointArn' \
  --output text)

# 2. Restore to test instance
aws backup start-restore-job \
  --recovery-point-arn $LATEST_BACKUP \
  --metadata file://test-restore-metadata.json \
  --iam-role-arn <BACKUP_ROLE_ARN> \
  --region us-west-1

# 3. Wait for restore
aws backup describe-restore-job --restore-job-id <JOB_ID>

# 4. Verify data integrity
psql -h test-gym-app-db.xyz.us-west-1.rds.amazonaws.com \
  -U gym_admin -d gymapp \
  -c "SELECT COUNT(*) FROM events;"

# 5. Delete test instance
aws rds delete-db-instance \
  --db-instance-identifier test-gym-app-db \
  --skip-final-snapshot \
  --region us-west-1

echo "✓ Backup restore test passed"
```

Run this monthly to ensure backups are valid.

---

## Monitoring & Alerts

### CloudWatch Alarms for Backup Failures

```yaml
# Add to CloudFormation:
BackupFailureAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${Environment}-gym-backup-failure'
    MetricName: NumberOfBackupJobsFailed
    Namespace: AWS/Backup
    Statistic: Sum
    Period: 3600
    EvaluationPeriods: 1
    Threshold: 1
    ComparisonOperator: GreaterThanOrEqualToThreshold
    AlarmActions:
      - !Ref SNSAlertTopic  # Send email/SMS on failure
```

### SNS Topic for Alerts

```yaml
SNSAlertTopic:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub '${Environment}-gym-backup-alerts'
    Subscription:
      - Endpoint: your-email@example.com
        Protocol: email
```

---

## Backup Security

### Encryption
- ✅ **At rest:** KMS encryption for backup vault
- ✅ **In transit:** SSL/TLS for all backup transfers
- ✅ **RDS storage:** Encrypted with AWS-managed keys

### Access Control
- ✅ **IAM Role:** Dedicated role for AWS Backup
- ✅ **Least privilege:** Only backup/restore permissions
- ✅ **MFA delete:** Require MFA to delete backups (optional)

### Backup Vault Lock (Optional)
Prevent deletion even by root account:

```bash
# Enable vault lock (irreversible!)
aws backup put-backup-vault-lock-configuration \
  --backup-vault-name prod-gym-app-vault \
  --min-retention-days 30 \
  --max-retention-days 365
```

---

## Recovery Procedures

### Quick Reference

| Data Loss | How Recent | Use | RTO | RPO |
|-----------|------------|-----|-----|-----|
| < 24 hours | Minutes ago | RDS PITR | 15 min | Seconds |
| 1-30 days | Last week | AWS Backup Daily | 20 min | 24 hours |
| 30-90 days | Last month | AWS Backup Weekly | 30 min | 7 days |
| 90-365 days | Last year | AWS Backup Monthly | 1 hour | 30 days |

### Full Disaster Recovery Runbook

1. **Identify issue** - What data was lost? When?
2. **Choose restore point** - Select appropriate backup
3. **Restore to new instance** - Don't overwrite production
4. **Verify data** - Check events, projections, users
5. **Test application** - Point staging app to restored DB
6. **Promote to production** - Update RDS Proxy target
7. **Update DNS** - If needed (usually automatic via proxy)

---

## Additional Recommendations

### 1. Export Critical Data to S3 (Long-term Archive)

```python
# Daily Lambda job: Export event log to S3
def export_events_to_s3():
    """Export yesterday's events to S3 for long-term archive."""
    events = get_events(limit=10000)  # Get all from yesterday
    
    s3.put_object(
        Bucket='gym-app-archives',
        Key=f'events/{date}/events.json.gz',
        Body=gzip.compress(json.dumps(events).encode())
    )
```

**Why:** S3 is cheaper for long-term storage, can enable Glacier for pennies/GB/year

### 2. Cross-Region Replication (High Availability)

For production, replicate monthly backups to us-east-1:

```yaml
CrossRegionCopy:
  DestinationBackupVaultArn: arn:aws:backup:us-east-1:ACCOUNT:vault/gym-app-vault-dr
  Lifecycle:
    MoveToColdStorageAfterDays: 30
    DeleteAfterDays: 365
```

**Cost:** Adds ~$0.02/GB for cross-region transfer + storage

### 3. Database Export for Migrations

Periodic logical dumps for version upgrades:

```bash
# Weekly pg_dump export
pg_dump -h prod-gym-app-proxy.us-west-1.rds.amazonaws.com \
  -U gym_admin -d gymapp \
  --format=custom \
  --file=gym_app_$(date +%Y%m%d).dump

# Upload to S3
aws s3 cp gym_app_$(date +%Y%m%d).dump \
  s3://gym-app-logical-backups/
```

---

## Restoration Testing Schedule

| Test Type | Frequency | Owner |
|-----------|-----------|-------|
| **Point-in-time restore** | Monthly | DevOps |
| **Snapshot restore** | Quarterly | DevOps |
| **Cross-region failover** | Annually | DevOps |
| **Full DR drill** | Annually | Engineering Team |

---

## Backup Metrics to Monitor

### CloudWatch Metrics

1. **Backup job success rate** - Should be 100%
2. **Backup job duration** - Track if backups are taking longer (DB growth)
3. **Backup storage used** - Monitor costs
4. **Failed restore tests** - Alert if monthly test fails

### Dashboard

```bash
# Get backup job stats
aws backup list-backup-jobs \
  --by-backup-vault-name prod-gym-app-vault \
  --by-created-after $(date -u -d '30 days ago' +%s) \
  --region us-west-1 \
  --query 'BackupJobs[?State==`FAILED`]'
```

---

## Costs Summary

### Early Stage (5 GB database)
- RDS Automated Backups: $0 (included)
- AWS Backup: ~$2/month
- **Total: ~$2/month**

### Growth (50 GB database)
- RDS Automated Backups: $0
- AWS Backup: ~$15/month
- **Total: ~$15/month**

### Production (100 GB database)
- RDS Automated Backups: $0
- AWS Backup: ~$25/month
- Cross-region copy: ~$10/month
- S3 archive: ~$5/month
- **Total: ~$40/month**

---

## Quick Commands

### List All Backups

```bash
# RDS automated snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier prod-gym-app-db \
  --region us-west-1

# AWS Backup recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name prod-gym-app-vault \
  --region us-west-1
```

### Restore Database (Emergency)

```bash
# Step 1: Restore from backup to new instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier prod-gym-app-db-emergency \
  --db-snapshot-identifier <SNAPSHOT_ID> \
  --db-instance-class db.t4g.micro \
  --region us-west-1

# Step 2: Wait for restore
aws rds wait db-instance-available \
  --db-instance-identifier prod-gym-app-db-emergency \
  --region us-west-1

# Step 3: Update RDS Proxy to point to new instance
aws rds modify-db-proxy-target-group \
  --db-proxy-name prod-gym-app-proxy \
  --target-group-name default \
  --new-name prod-gym-app-db-emergency \
  --region us-west-1

# Your app is now using the restored database (no code changes!)
```

---

## Backup Best Practices

### ✅ DO

1. **Test restores monthly** - Backups are useless if they don't restore
2. **Monitor backup jobs** - Set up CloudWatch alarms
3. **Tag backups** - Use Environment, Application tags
4. **Encrypt everything** - Use KMS for backup vault
5. **Document procedures** - Keep runbooks up-to-date
6. **Separate backup IAM role** - Least privilege principle
7. **Keep long-term archives** - Monthly backups for 1 year

### ❌ DON'T

1. **Don't rely on one backup tier** - Use multiple (RDS + AWS Backup)
2. **Don't delete old backups manually** - Let lifecycle policies handle it
3. **Don't skip restore testing** - You'll regret it during a real incident
4. **Don't store backups in same region only** - Cross-region for DR
5. **Don't forget to backup exercise library** - `data/exercises.json` in git + S3

---

## Backup Compliance

### Data Retention Requirements

| Data Type | Retention | Reason |
|-----------|-----------|--------|
| **User workouts** | Indefinite | User property |
| **Event log** | Indefinite | Audit trail |
| **Projections** | Rebuilable | Can regenerate from events |
| **Database backups** | 30 days (automated), 1 year (monthly) | Recovery window |

### GDPR / Privacy Considerations

If user requests data deletion:
- Delete from primary database
- Backups will age out naturally (don't need immediate deletion from backups per GDPR)
- Document this in privacy policy

---

## Future Enhancements

### Phase 2: As You Grow

1. **Read Replica** - For analytics queries (offload primary)
2. **Multi-AZ Deployment** - Automatic failover (~2x cost)
3. **Cross-Region Read Replica** - Global availability
4. **S3 Archival** - Export old workouts to Glacier Deep Archive ($0.00099/GB/month)

### Phase 3: Enterprise Scale

1. **Aurora PostgreSQL** - Better performance, auto-scaling
2. **Aurora Global Database** - Multi-region active-active
3. **Continuous Backup** - Point-in-time to any millisecond
4. **Automated DR Testing** - Chaos engineering tests

---

## Monitoring Dashboard Queries

### Backup Health Check

```sql
-- Check last successful backup
SELECT 
  MAX(completed_at) as last_backup,
  COUNT(*) as total_backups_last_30_days
FROM aws_backup_jobs
WHERE status = 'COMPLETED'
  AND created_at > NOW() - INTERVAL '30 days';
```

### Database Size Trend

```bash
# Track DB growth for capacity planning
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value=prod-gym-app-db \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average \
  --region us-west-1
```

---

## Deployment

The CloudFormation template now includes:
- ✅ 30-day RDS automated backups
- ✅ AWS Backup vault (encrypted)
- ✅ 3-tier backup plan (daily/weekly/monthly)
- ✅ Automatic lifecycle management
- ✅ IAM roles for backup service

Deploy with:
```bash
aws cloudformation create-stack \
  --stack-name gym-app-prod \
  --template-body file://infrastructure/cloudformation-template.yaml \
  --parameters file://infrastructure/deploy-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region us-west-1
```

Backups start automatically after stack creation!



