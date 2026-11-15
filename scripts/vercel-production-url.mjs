// Print `url=https://...` for the public production domain of a Vercel deployment/project.
// Unique deployment URLs can sit behind Vercel Authentication; the production alias is public.
const token = process.env.VERCEL_TOKEN;
const args = process.argv.slice(2);
const flag = (name) => { const index = args.indexOf(name); return index >= 0 ? args[index + 1] : ""; };
const deployment = flag("--deployment");
const project = flag("--project");
const team = process.env.VERCEL_ORG_ID && process.env.VERCEL_ORG_ID.startsWith("team_") ? `teamId=${process.env.VERCEL_ORG_ID}` : "";

async function api(path) {
  const response = await fetch(`https://api.vercel.com${path}${path.includes("?") ? "&" : "?"}${team}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`Vercel API ${response.status}`);
  return response.json();
}

function pick(aliases) {
  const public_ = aliases.filter((alias) => alias && !/-[a-z0-9]{9}-/.test(alias)).sort((a, b) => a.length - b.length);
  return public_[0] || aliases[0];
}

try {
  let host = "";
  if (deployment) {
    const id = deployment.replace(/^https?:\/\//, "").replace(/\/$/, "");
    const data = await api(`/v13/deployments/${encodeURIComponent(id)}`);
    host = pick(data.alias || []) || data.url;
  } else if (project) {
    const data = await api(`/v9/projects/${encodeURIComponent(project)}`);
    const aliases = (data.targets?.production?.alias || data.alias?.map((item) => item.domain) || []);
    host = pick(aliases);
  }
  if (!host) throw new Error("production alias not found");
  console.log(`url=https://${host.replace(/^https?:\/\//, "")}`);
} catch (error) {
  console.error(`::warning::${error.message}`);
  console.log(`url=${deployment || ""}`);
}
