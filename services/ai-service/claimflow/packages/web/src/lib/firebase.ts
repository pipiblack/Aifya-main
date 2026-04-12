import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAnalytics, logEvent as firebaseLogEvent, type Analytics } from 'firebase/analytics';

const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

let analytics: Analytics | null = null;

export const initAnalytics = () => {
    if (typeof window !== 'undefined') {
        const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
        if (firebaseConfig.measurementId) {
            analytics = getAnalytics(app);
        }
    }
};

export const logEvent = (eventName: string, eventParams?: Record<string, any>) => {
    if (analytics) {
        firebaseLogEvent(analytics, eventName, eventParams);
    }
};

// Typed helpers for common events
export const logLogin = (tenantId: string, role: string) => {
    logEvent('login', {
        method: 'email',
        tenant_id: tenantId,
        user_role: role,
    });
};

export const logClaimCreated = (tenantId: string, facilityId: string, claimType: string) => {
    logEvent('claim_created', {
        tenant_id: tenantId,
        facility_id: facilityId,
        claim_type: claimType,
    });
};

export const logAuditTriggered = (tenantId: string, claimId: string) => {
    logEvent('audit_triggered', {
        tenant_id: tenantId,
        claim_id: claimId,
    });
};
