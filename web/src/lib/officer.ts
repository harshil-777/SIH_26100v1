// The officer's name, as last typed into a decision form. There is no login, so this is only a
// convenience default; storage can be blocked (private windows), hence the try/catch.
const OFFICER_KEY = "gem.officer";

export function readOfficer(): string {
  try {
    return localStorage.getItem(OFFICER_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberOfficer(name: string) {
  try {
    localStorage.setItem(OFFICER_KEY, name);
  } catch {
    // Storage blocked -- the officer just retypes their name next time.
  }
}
