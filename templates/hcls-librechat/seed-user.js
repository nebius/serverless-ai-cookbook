/* Deployment-only convenience: create/update one local-login user when
 * SEED_DEFAULT_USER_EMAIL and SEED_DEFAULT_USER_PASSWORD are set. Guarded so
 * normal deployments are unaffected. Runs after migrations/seed, before API. */
const { MongoClient } = require('mongodb');
const bcrypt = require('bcryptjs');
const { encrypt } = require('@librechat/api');

const email = process.env.SEED_DEFAULT_USER_EMAIL;
const password = process.env.SEED_DEFAULT_USER_PASSWORD;

if (!email || !password) {
  process.exit(0);
}

(async () => {
  const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat';
  const client = new MongoClient(uri, { serverSelectionTimeoutMS: 30000 });
  await client.connect();
  try {
    const users = client.db().collection('users');
    const hashed = await bcrypt.hash(password, 10);
    const now = new Date();
    const result = await users.updateOne(
      { email },
      {
        $set: {
          email,
          emailVerified: true,
          name: email.split('@')[0],
          username: email.split('@')[0],
          password: hashed,
          provider: 'local',
          role: 'USER',
          updatedAt: now,
        },
        $setOnInsert: { createdAt: now },
      },
      { upsert: true },
    );
    const user = await users.findOne({ email }, { projection: { _id: 1 } });
    if (!user) throw new Error('Unable to resolve the seeded default user');

    // A dedicated deployment already receives this credential from
    // MysteryBox. Seed the same key into LibreChat's user-scoped MCP store so
    // a replacement endpoint is usable immediately. Preserve a key the user
    // later changed in Apps settings; restarts must not overwrite it.
    let credentialSeeded = false;
    if (process.env.SCIENTIFIC_MODELS_API_KEY) {
      const authField = 'SCIENTIFIC_MODELS_API_KEY';
      const pluginKey = 'mcp_scientific-demos';
      const encryptedValue = await encrypt(process.env.SCIENTIFIC_MODELS_API_KEY);
      const credential = await client.db().collection('pluginauths').updateOne(
        { userId: String(user._id), authField, pluginKey },
        {
          $setOnInsert: {
            userId: String(user._id), authField, pluginKey,
            value: encryptedValue, createdAt: now, updatedAt: now,
          },
        },
        { upsert: true },
      );
      credentialSeeded = Boolean(credential.upsertedId);
    }
    console.log(
      `[seed-user] ${result.upsertedId ? 'created' : 'updated'} default user ${email}`,
    );
    if (process.env.SCIENTIFIC_MODELS_API_KEY) {
      console.log(`[seed-user] ${credentialSeeded ? 'seeded' : 'retained'} default user Scientific AI workbench credential`);
    }
  } finally {
    await client.close();
  }
})().catch((error) => {
  console.error('[seed-user] failed:', error.message);
  process.exit(1);
});
