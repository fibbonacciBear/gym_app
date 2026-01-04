# Auth0 Quick Start - Follow These Steps

## 🚀 What I've Prepared

✅ **CloudFormation template updated** with:
- NAT Gateway (for Lambda internet access)
- Auth0 parameters (Domain, Client ID, Audience)
- Auth0 environment variables for Lambda

✅ **Deploy parameters file** ready at:
- `infrastructure/deploy-parameters-simple-staging.json`

---

## 📋 Your Action Items

### **1. Create Auth0 Account & Application (5 minutes)**

Go to: https://auth0.com/ → Sign Up (free)

Create a **Single Page Application** named "Gym App - Staging"

---

### **2. Get These 3 Values**

From Auth0 Dashboard → Applications → Your App:
- ✍️ **Domain**: `_____________.us.auth0.com`
- ✍️ **Client ID**: `_________________________`

From Auth0 Dashboard → APIs → Create API:
- ✍️ **Audience**: `https://api.gymapp.com` (your choice)

---

### **3. Configure Auth0 Application**

In your Auth0 application settings, add:

**Allowed Callback URLs:**
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
```

**Allowed Logout URLs:**
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
```

**Allowed Web Origins:**
```
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws
```

---

### **4. Update Deployment Parameters**

Edit: `infrastructure/deploy-parameters-simple-staging.json`

Replace the three empty Auth0 values with your credentials from step 2.

---

### **5. Deploy**

```bash
cd /Users/akashganesan/Documents/code/gym_app
./deploy-simple.sh
```

Wait ~8 minutes (NAT Gateway creation takes time).

---

### **6. Test**

Open: https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/

Click "Log In" → Should see Auth0 login page ✅

---

## 💰 Cost Impact

**NAT Gateway**: ~$32/month (required for Auth0 token validation)

**Alternative**: If you want to avoid NAT Gateway costs, we could:
- Use VPC Endpoints for specific services (~$7/month per endpoint)
- Move Lambda to public subnets (less secure, not recommended)

---

## 📚 Full Documentation

See: `AUTH0_SETUP_GUIDE.md` for detailed step-by-step instructions with screenshots and troubleshooting.

---

**Ready to proceed?** Start with step 1! 🚀

