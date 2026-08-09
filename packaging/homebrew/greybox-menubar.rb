cask "greybox-menubar" do
  version "0.1.0"
  sha256 "FILL_IN_AFTER_FIRST_RELEASE_ZIP"

  url "https://github.com/Saachi30/greybox/releases/download/v#{version}/Greybox.app.zip"
  name "Greybox"
  desc "Menu bar companion for the greybox pentesting assistant"
  homepage "https://github.com/Saachi30/greybox"

  depends_on macos: ">= :ventura"

  app "Greybox.app"

  zap trash: [
    "~/Library/Preferences/dev.greybox.menubar.plist",
  ]
end
