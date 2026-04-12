import { getPool } from '../db/client.js';
import { loadConfig } from '../config.js';
import bcrypt from 'bcryptjs';
import pino from 'pino';

async function main() {
    const config = loadConfig();
    const logger = pino({ level: config.LOG_LEVEL });
    const pool = getPool(config);

    const args = process.argv.slice(2);
    const params: Record<string, string> = {};

    for (let i = 0; i < args.length; i += 2) {
        const keyArg = args[i];
        if (keyArg) {
            const key = keyArg.replace('--', '');
            const value = args[i + 1];
            if (value) {
                params[key] = value;
            }
        }
    }

    const {
        'tenant-name': tenantName,
        'tenant-slug': tenantSlug,
        'facility-name': facilityName,
        'facility-code': facilityCode,
        'admin-email': adminEmail,
        'admin-password': adminPassword,
        'tier': tier = 'LEVEL_4',
        'county': county = 'UNKNOWN',
    } = params;

    if (!tenantName || !tenantSlug || !facilityName || !facilityCode || !adminEmail || !adminPassword) {
        console.error('Usage: npm run onboard -- --tenant-name "Hospital" --tenant-slug "hosp" --facility-name "Main" --facility-code "FID123" --admin-email "admin@hosp.com" --admin-password "Pass123"');
        process.exit(1);
    }

    try {
        logger.info({ tenantName, tenantSlug }, 'Starting onboarding...');

        // 1. Create Tenant
        const tenantResult = await pool.query(
            `INSERT INTO tenants (name, slug) VALUES ($1, $2) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id`,
            [tenantName, tenantSlug]
        );
        const tenantId = tenantResult.rows[0].id;

        // 2. Create Facility
        const facilityResult = await pool.query(
            `INSERT INTO facilities (tenant_id, name, sha_facility_code, tier_level, county, status) 
       VALUES ($1, $2, $3, $4, $5, 'ACTIVE') 
       ON CONFLICT (tenant_id, sha_facility_code) DO UPDATE SET name = EXCLUDED.name RETURNING id`,
            [tenantId, facilityName, facilityCode, tier, county]
        );
        const facilityId = facilityResult.rows[0].id;

        // 3. Create Admin User
        const passwordHash = await bcrypt.hash(adminPassword, 12);
        await pool.query(
            `INSERT INTO users (tenant_id, facility_id, email, display_name, password_hash, role, must_change_password)
       VALUES ($1, $2, lower($3), 'Administrator', $4, 'admin', true)
       ON CONFLICT (tenant_id, email) DO UPDATE SET password_hash = EXCLUDED.password_hash`,
            [tenantId, facilityId, adminEmail, passwordHash]
        );

        // 4. Setup License
        await pool.query(
            `INSERT INTO license_state (facility_id, tier, license_token, expires_at)
       VALUES ($1, $2, $3, now() + INTERVAL '30 days')
       ON CONFLICT (facility_id) DO NOTHING`,
            [facilityId, tier, `trial-${Math.random().toString(36).substring(2, 15)}`]
        );

        logger.info('✅ Onboarding complete!');
        process.exit(0);
    } catch (error) {
        logger.error({ err: error }, 'Onboarding failed');
        process.exit(1);
    }
}

main();
