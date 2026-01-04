# Adding Custom Domain - Auth0 Update Required

## ⚠️ **IMPORTANT: Update Auth0 Callback URLs**

Your app will be accessible at: **`https://staging.titantrakr.com`**

### **Before Deployment:**

Go to Auth0 Dashboard → Applications → TitanTrakr → Settings

**Update these fields to include the new domain:**

### **Allowed Callback URLs:**
```
https://staging.titantrakr.com/
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
http://localhost:8000
```

### **Allowed Logout URLs:**
```
https://staging.titantrakr.com/
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/
http://localhost:8000
```

### **Allowed Web Origins:**
```
https://staging.titantrakr.com
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws
http://localhost:8000
```

### **Allowed Origins (CORS):**
```
https://staging.titantrakr.com
https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws
http://localhost:8000
```

Click **Save Changes**!

---

## Then Deploy

```bash
cd /Users/akashganesan/Documents/code/gym_app
./deploy-simple.sh
```

**Expected time**: ~15-20 minutes (SSL certificate validation + CloudFront distribution)

---

## After Deployment

Your app will be available at both:
- ✅ **https://staging.titantrakr.com** (CloudFront CDN - FAST!)
- ✅ **https://j6twzcgsi73mnqnvgmubabmuee0doxnw.lambda-url.us-west-1.on.aws/** (Lambda URL - still works)

The custom domain will be faster and have a better URL! 🚀

