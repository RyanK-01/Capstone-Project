"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from '@/app/components/AuthContext';
import { useFeedback } from "../components/FeedbackContext";


export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [full_name, setFull_name] = useState("");
  const [role, setRole] = useState("");
  const { login } = useAuth();
  const { setMsg } = useFeedback();

  const router = useRouter();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMsg("", true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          password: password,
          full_name: full_name,
          role: role
        })
      });

      if (response.status !== 201) {
        const data = await response.json();
        if (response.status === 400) {
          setMsg(data.detail || "Email already registered or password too weak.", true);
        }
        else if (response.status === 422) {
          setMsg("Invalid email format or missing fields", true);
        }
        else {
          setMsg(data.detail || "Request failed", true);
          throw new Error(data.detail || 'Request failed');
        }
        return;
      }


      const loginResponse = await fetch('/api/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          password: password,
        })
      });

      if (!loginResponse.ok) {
        const data = await loginResponse.json();
        if (loginResponse.status === 401) {
          setMsg(data.detail || "Invalid credentials", true);
        }
        else if (loginResponse.status === 403) {
          setMsg(data.detail || "Account disabled", true);
        }
        else {
          setMsg(data.detail || "Request failed", true);
          throw new Error(data.detail || 'Request failed');
        }
        return;
      }

      const { access_token, user } = await loginResponse.json();

      login(user, access_token);

      router.push('/sessions');

      setMsg("Registration successful", false);

    } catch (error) {
      setMsg((error instanceof Error) ? error.message : "Error", true);
      console.error("Error: ", error);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow-md"
      >
        <h1 className="text-center text-3xl font-bold">
          Create an Account
        </h1>

        <div>
          <label
            htmlFor="full_name"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            Full Name
          </label>

          <input
            id="full_name"
            type="text"
            value={full_name}
            onChange={(event) => setFull_name(event.target.value)}
            required
            className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label
            htmlFor="email"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            Email Address
          </label>

          <input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            Password
          </label>

          <input
            id="password"
            minLength={8}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label
            htmlFor="role"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            Role
          </label>

          <select
            id="role"
            value={role}
            onChange={(event) => setRole(event.target.value)}
            required
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Select a role</option>
            <option value="student">Student</option>
            <option value="ta">Teaching Assistant</option>
            <option value="instructor">Instructor</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        <button
          type="submit"
          className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
        >
          Register
        </button>
      </form>
    </main>
  );
}
