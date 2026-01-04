# Auth0 Setup Guide for Gym App

This guide walks you through setting up Auth0 authentication for your gym app.

---

## Step 1: Create Auth0 Account (if you don't have one)

1. Go to https://auth0.com/
2. Click "Sign Up" (free tier available)
3. Choose a tenant name (e.g., `gym-app` or your company name)
4. Select your region (e.g., US)

---

## Step 2: Create an Auth0 Application

1. Log in to [Auth0 Dashboard](https://manage.auth0.com/)
2. Click **Applications** → **Applications** in the left sidebar
3. Click **Create Application**
4. Fill in:
   - **Name**: `Gym App - Staging`
   - **Application Type**: `Single Page Application (SPA)`
5. Click **Create**

---

## Step 3: Configure Application Settings

In your new application's settings tab:

### **Allowed Callback URLs**
Add your Lambda Function URL:
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/callback
```

### **Allowed Logout URLs**
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
```

### **Allowed Web Origins**
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws
```

### **Allowed Origins (CORS)**
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws
```

Click **Save Changes** at the bottom.

---

## Step 4: Create an Auth0 API

1. Go to **Applications** → **APIs** in the left sidebar
2. Click **Create API**
3. Fill in:
   - **Name**: `Gym App API`
   - **Identifier** (Audience): `https://api.gymapp.com` (or your own identifier)
   - **Signing Algorithm**: `RS256`
4. Click **Create**

> **Note**: The "Identifier" becomes your Auth0 Audience. It's just a unique identifier, not an actual URL that needs to exist.

---

## Step 5: Get Your Auth0 Credentials

### **From your Application:**
1. Go to **Applications** → **Applications** → `Gym App - Staging`
2. Note down:
   - **Domain**: (e.g., `dev-abc123.us.auth0.com`)
   - **Client ID**: (e.g., `xYz123AbC456...`)

### **From your API:**
1. Go to **Applications** → **APIs** → `Gym App API`
2. Note down:
   - **Identifier** (Audience): (e.g., `https://api.gymapp.com`)

---

## Step 6: Update Deployment Parameters

Edit `infrastructure/deploy-parameters-simple-staging.json` and fill in your Auth0 credentials:

```json
{
  "ParameterKey": "Auth0Domain",
  "ParameterValue": "dev-abc123.us.auth0.com"  // YOUR DOMAIN (without https://)
},
{
  "ParameterKey": "Auth0ClientId",
  "ParameterValue": "xYz123AbC456..."  // YOUR CLIENT ID
},
{
  "ParameterKey": "Auth0Audience",
  "ParameterValue": "https://api.gymapp.com"  // YOUR API IDENTIFIER
}
```

---

## Step 7: Deploy Infrastructure Update

Run the deployment script to update your CloudFormation stack with NAT Gateway and Auth0 config:

```bash
./deploy-staging.sh
```

This will:
- ✅ Add NAT Gateway (costs ~$32/month)
- ✅ Enable Lambda internet access
- ✅ Pass Auth0 credentials to Lambda

**Expected time**: ~5-8 minutes (NAT Gateway takes a few minutes to create)

---

## Step 8: Test Authentication

1. Open your app: https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
2. Click **Log In**
3. You should see Auth0's login page
4. Create an account or log in
5. After login, you'll be redirected back to your app with authentication

---

## Step 9: Create Test User (Optional)

To test without social login:

1. Go to **User Management** → **Users** in Auth0 Dashboard
2. Click **Create User**
3. Fill in:
   - **Email**: `test@example.com`
   - **Password**: (create a strong password)
   - **Connection**: `Username-Password-Authentication`
4. Click **Create**

Now you can log in with this test user.

---

## Cost Breakdown

### **New AWS Costs (NAT Gateway)**:
- **NAT Gateway**: ~$0.045/hour = **~$32/month**
- **Data Transfer**: ~$0.045/GB processed

### **Auth0 Costs**:
- **Free Tier**: Up to 7,000 active users/month
- **After that**: Paid plans start at $35/month

---

## Troubleshooting

### **"Callback URL mismatch" error**
- Verify the Lambda Function URL is in Auth0's **Allowed Callback URLs**
- Make sure there are no trailing slashes if you didn't include them

### **"Audience is invalid" error**
- Check that `Auth0Audience` in your parameters matches the API Identifier exactly

### **Still getting "Not authenticated" errors**
- Check Lambda logs: `aws logs tail /aws/lambda/staging-gym-app --since 5m --region us-west-1`
- Verify NAT Gateway is deployed and Lambda has internet access

---

## Summary

You've configured:
- ✅ Auth0 tenant and application
- ✅ Auth0 API with audience
- ✅ NAT Gateway for Lambda internet access
- ✅ Auth0 credentials in CloudFormation
- ✅ Callback URLs and CORS settings

Your app now supports secure authentication! 🎉

