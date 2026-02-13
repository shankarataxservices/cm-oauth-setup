 const { google } = require('googleapis');
const fs = require('fs');

const creds = JSON.parse(fs.readFileSync('./client_secret.json', 'utf8')).installed;

const SCOPES = [
  'https://www.googleapis.com/auth/calendar',
  'https://www.googleapis.com/auth/gmail.send',
  'https://www.googleapis.com/auth/drive.file',
];

(async () => {
  const oAuth2Client = new google.auth.OAuth2(
    creds.client_id,
    creds.client_secret,
    creds.redirect_uris[0]
  );

  const url = oAuth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: SCOPES,
    prompt: 'consent',
  });

  console.log('Open this URL:\n', url);

  const rl = require('readline').createInterface({ input: process.stdin, output: process.stdout });
  rl.question('\nPaste code here: ', async (code) => {
    rl.close();
    const { tokens } = await oAuth2Client.getToken(code);
    console.log('\nREFRESH TOKEN:\n', tokens.refresh_token);
  });
})();
