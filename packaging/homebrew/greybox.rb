class Greybox < Formula
  include Language::Python::Virtualenv

  desc "Local, natural-language pentesting assistant CLI"
  homepage "https://github.com/Saachi30/greybox"
  url "https://github.com/Saachi30/greybox/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "FILL_IN_AFTER_FIRST_RELEASE_TARBALL"
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install_and_link buildpath/"cli"
  end

  test do
    system "#{bin}/greybox", "--help"
  end
end
