document.addEventListener("DOMContentLoaded", async () => {
  const token = localStorage.getItem("token")

  if (!token) {
    window.location.href = "login.html"
    return
  }

  const res = await fetch("http://127.0.0.1:8000/me", {
    headers: {
      Authorization: "Bearer " + token
    }
  })

  const user = await res.json()

  if (user.plan === "free") {
    const links = document.querySelectorAll("#sidebar .nav-link")

    links.forEach(link => {
      const text = link.innerText.toLowerCase()

      if (
        text.includes("transaction") ||
        text.includes("lien") ||
        text.includes("api") ||
        text.includes("multi")
      ) {
        link.style.opacity = "0.5"
        link.style.cursor = "not-allowed"

        link.addEventListener("click", (e) => {
            e.preventDefault()
            console.log("CLICK OK")
            showUpgradeModal() // TA popup
        })
    
      }
    })
  }
})