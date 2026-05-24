# Agama, jeos-firstboot, and YaST

This project touches three different openSUSE setup/configuration systems. They are related, but they run at different points in the user journey.

## Summary

| System | What it is | When it runs | Project role |
|---|---|---|---|
| Agama | New web-based installer stack | Install time, before the installed system boots | Leap 16 install-time integration path |
| jeos-firstboot | Lightweight first-boot setup framework for JeOS/appliance images | First boot after installation/image boot | User opt-in onboarding hook |
| YaST | Traditional openSUSE installer and system administration framework | Install time and after installation | Topic the assistant teaches; possible future integration |

## Agama

Agama is the newer web-based installer for openSUSE and SUSE systems. It is especially important for Leap 16 and later.

For this project, Agama is not the assistant itself. Agama is the install-time place where the system can be prepared so the assistant is available after installation.

The first PoC should prove:

```text
Agama install profile/script
  -> install or enable suse-assist
  -> installed system boots
  -> AI onboarding is available
```

Current scope:

- Use Agama profile/script support.
- Install or enable `suse-assist.socket` or a firstboot service.
- Keep the PoC simple and non-invasive.

Out of scope for the first PoC:

- Native Agama UI module.
- Embedded chat inside the installer.
- Any cloud AI dependency.

## jeos-firstboot

`jeos-firstboot` is a lightweight first-boot configuration framework used by JeOS and appliance-style images.

It runs after the installed image boots for the first time. That makes it a natural place to ask the user whether they want to start the AI onboarding assistant.

The first PoC should prove:

```text
First boot starts
  -> jeos-firstboot module runs
  -> user is asked to opt in
  -> suse-assist starts in CLI or web mode
```

This is the best user-facing onboarding hook because the user is now inside the installed system, where system context detection is meaningful.

## YaST

YaST is the classic openSUSE installer and system administration framework.

It matters to this project in two ways:

1. New users need help understanding YaST.
2. YaST remains an important openSUSE administration tool after installation.

For the first GSoC implementation, YaST should primarily be treated as assistant knowledge:

```text
User asks: "How do I configure firewall?"
Assistant answers: "Use YaST Firewall or firewall-cmd..."
```

A native YaST integration can be considered later, but it is not the shortest path to proving the onboarding assistant.

## Recommended Flow

The practical integration flow is:

```text
Agama
  install-time preparation for Leap 16
  installs/enables suse-assist or firstboot hook

jeos-firstboot
  first-boot opt-in user experience
  starts assistant when the user wants help

suse-assist
  local SLM + RAG assistant
  explains zypper, YaST, Snapper, Btrfs, networking, repositories

YaST
  system administration tool that users learn through the assistant
```

## Decision

For GSoC, build in this order:

1. `suse-assist` core assistant and model routing.
2. `jeos-firstboot` opt-in module.
3. Agama Leap 16 profile/script PoC that enables the assistant for first boot.
4. YaST guidance inside the assistant.
5. Native Agama or YaST UI integration only after the basic install/firstboot flow works.

This order gives mentors a working end-to-end story without overcommitting to installer UI work too early.
