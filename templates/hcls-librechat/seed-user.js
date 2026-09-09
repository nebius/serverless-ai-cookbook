/* Deployment-only convenience: create/update one local-login user when
 * SEED_DEFAULT_USER_EMAIL and SEED_DEFAULT_USER_PASSWORD are set. Guarded so
 * normal deployments are unaffected. Runs after migrations/seed, before API. */
const { MongoClient } = require('mongodb');
const bcrypt = require('bcryptjs');

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
    console.log(
      `[seed-user] ${result.upsertedId ? 'created' : 'updated'} default user ${email}`,
    );
  } finally {
    await client.close();
  }
})().catch((error) => {
  console.error('[seed-user] failed:', error.message);
  process.exit(1);
});
