document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const signupContainer = document.getElementById("signup-container");
  const messageDiv = document.getElementById("message");
  const authButton = document.getElementById("auth-button");
  const authButtonLabel = document.getElementById("auth-button-label");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  let teacherUsername = null;

  function showMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.classList.remove("hidden");

    setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  function updateAuthUI() {
    const isTeacher = Boolean(teacherUsername);
    signupContainer.hidden = !isTeacher;
    authButtonLabel.textContent = isTeacher
      ? `Sign out (${teacherUsername})`
      : "Teacher Login";
    authButton.setAttribute(
      "aria-label",
      isTeacher ? "Sign out" : "Teacher login"
    );
  }

  async function refreshAuthState() {
    const response = await fetch("/auth/me");
    if (response.status === 401) {
      teacherUsername = null;
      updateAuthUI();
      return;
    }
    if (!response.ok) {
      throw new Error("Could not check teacher login status.");
    }

    const result = await response.json();
    teacherUsername = result.username;
    updateAuthUI();
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error("Could not load activities.");
      }
      const activities = await response.json();
      activitiesList.replaceChildren();
      activitySelect.replaceChildren(activitySelect.options[0]);

      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const title = document.createElement("h4");
        title.textContent = name;
        activityCard.appendChild(title);

        const description = document.createElement("p");
        description.textContent = details.description;
        activityCard.appendChild(description);

        const schedule = document.createElement("p");
        const scheduleLabel = document.createElement("strong");
        scheduleLabel.textContent = "Schedule: ";
        schedule.append(scheduleLabel, details.schedule);
        activityCard.appendChild(schedule);

        const availability = document.createElement("p");
        const availabilityLabel = document.createElement("strong");
        availabilityLabel.textContent = "Availability: ";
        availability.append(
          availabilityLabel,
          `${details.max_participants - details.participants.length} spots left`
        );
        activityCard.appendChild(availability);

        const participantsContainer = document.createElement("div");
        participantsContainer.className = "participants-container";
        if (details.participants.length > 0) {
          const participantsSection = document.createElement("div");
          participantsSection.className = "participants-section";
          const participantsTitle = document.createElement("h5");
          participantsTitle.textContent = "Participants:";
          const participantsList = document.createElement("ul");
          participantsList.className = "participants-list";

          details.participants.forEach((email) => {
            const participant = document.createElement("li");
            const participantEmail = document.createElement("span");
            participantEmail.className = "participant-email";
            participantEmail.textContent = email;
            participant.appendChild(participantEmail);

            if (teacherUsername) {
              const unregisterButton = document.createElement("button");
              unregisterButton.className = "delete-btn";
              unregisterButton.type = "button";
              unregisterButton.textContent = "Remove";
              unregisterButton.setAttribute(
                "aria-label",
                `Unregister ${email} from ${name}`
              );
              unregisterButton.addEventListener("click", () =>
                handleUnregister(name, email)
              );
              participant.appendChild(unregisterButton);
            }

            participantsList.appendChild(participant);
          });
          participantsSection.append(participantsTitle, participantsList);
          participantsContainer.appendChild(participantsSection);
        } else {
          const emptyParticipants = document.createElement("p");
          const emptyText = document.createElement("em");
          emptyText.textContent = "No participants yet";
          emptyParticipants.appendChild(emptyText);
          participantsContainer.appendChild(emptyParticipants);
        }
        activityCard.appendChild(participantsContainer);
        activitiesList.appendChild(activityCard);

        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });
    } catch (error) {
      activitiesList.textContent =
        "Failed to load activities. Please try again later.";
      console.error("Error fetching activities:", error);
    }
  }

  async function handleUnregister(activity, email) {
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        await fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      console.error("Error unregistering:", error);
      showMessage("Failed to unregister. Please try again.", "error");
    }
  }

  authButton.addEventListener("click", async () => {
    if (!teacherUsername) {
      loginError.classList.add("hidden");
      loginDialog.showModal();
      return;
    }

    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      if (!response.ok) {
        throw new Error("Could not sign out.");
      }
      teacherUsername = null;
      updateAuthUI();
      await fetchActivities();
      showMessage("Signed out.", "success");
    } catch (error) {
      console.error("Error signing out:", error);
      showMessage("Failed to sign out. Please try again.", "error");
    }
  });

  document
    .getElementById("close-login")
    .addEventListener("click", () => loginDialog.close());

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginError.classList.add("hidden");
    const formData = new FormData(loginForm);

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Unable to log in.");
      }

      teacherUsername = result.username;
      loginForm.reset();
      loginDialog.close();
      updateAuthUI();
      await fetchActivities();
      showMessage(`Signed in as ${teacherUsername}.`, "success");
    } catch (error) {
      loginError.textContent = error.message;
      loginError.classList.remove("hidden");
    }
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!teacherUsername) {
      showMessage("Teacher login is required to sign up students.", "error");
      return;
    }

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        signupForm.reset();
        // Refresh activities list to show updated participants
        await fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      console.error("Error signing up:", error);
      showMessage("Failed to sign up. Please try again.", "error");
    }
  });

  refreshAuthState()
    .catch((error) => {
      console.error("Error checking teacher login:", error);
      showMessage("Could not check teacher login status.", "error");
    })
    .finally(fetchActivities);
});
