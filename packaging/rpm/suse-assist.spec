#
# Draft native RPM spec for suse-assist.
#
# This is a packaging scaffold, not yet a Factory-ready package. The runtime
# needs Python packages that are not currently available as openSUSE RPMs
# (notably llama-cpp-python, lancedb, sentence-transformers/transformers,
# gradio, and mcp). Do not submit this spec to Factory until those dependencies
# are packaged or an approved vendoring approach is chosen.
#

Name:           suse-assist
Version:        0.1.0
Release:        0
Summary:        Local AI onboarding assistant for openSUSE Leap
License:        MIT
URL:            https://github.com/anujagrawal380/openSUSE-leap-ai-startup-guide
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python-rpm-macros

Requires:       python3
Requires:       python3-click
Requires:       python3-PyYAML
Requires:       python3-psutil
Requires:       python3-requests
Requires:       python3-rich

# Missing runtime dependencies to package or vendor before this can build/run:
# Requires:     python3-gradio
# Requires:     python3-huggingface-hub
# Requires:     python3-lancedb
# Requires:     python3-langchain
# Requires:     python3-langchain-community
# Requires:     python3-langchain-text-splitters
# Requires:     python3-llama-cpp-python
# Requires:     python3-mcp
# Requires:     python3-sentence-transformers
# Requires:     python3-transformers

%description
suse-assist is a local, private AI onboarding assistant for openSUSE Leap. It
combines a local small language model, a LanceDB-backed documentation index, and
host system context detection to answer setup and troubleshooting questions.

%prep
%autosetup -n %{name}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install

install -D -m 0644 deploy/suse-assist.service \
  %{buildroot}%{_unitdir}/suse-assist.service
install -D -m 0755 packaging/desktop/suse-assist-launcher.sh \
  %{buildroot}%{_bindir}/suse-assist-launcher
install -D -m 0644 packaging/desktop/suse-assist.desktop \
  %{buildroot}%{_datadir}/applications/suse-assist.desktop
install -D -m 0644 packaging/desktop/icons/hicolor/scalable/apps/suse-assist.svg \
  %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/suse-assist.svg

%files
%license LICENSE
%doc README.md docs
%{_bindir}/suse-assist
%{_bindir}/suse-assist-launcher
%{python3_sitelib}/opensuse_ai
%{python3_sitelib}/opensuse_leap_ai_guide-*.dist-info
%{_unitdir}/suse-assist.service
%{_datadir}/applications/suse-assist.desktop
%{_datadir}/icons/hicolor/scalable/apps/suse-assist.svg

%changelog
