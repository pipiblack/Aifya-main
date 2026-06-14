"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail, Activity, ArrowRight, AlertCircle, Loader2 } from "lucide-react";

export default function LoginPage() {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isHovered, setIsHovered] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError("");

        try {
            const res = await fetch("/next-api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            let data;
            const textResponse = await res.text();

            try {
                data = JSON.parse(textResponse);
            } catch (jsonErr) {
                // If it isn't JSON, it might be an HTML error page from Nginx or Next.js
                throw new Error(`Server Error (${res.status}): ${textResponse.slice(0, 80)}...`);
            }

            if (!res.ok) {
                setError(data.error || "Login failed");
            } else {
                window.location.href = "/";
            }
        } catch (err: any) {
            setError(err.message || "An unexpected error occurred.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center relative overflow-hidden">
            {/* Background Micro-animations and Gradients */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
                <div className="absolute -top-[40%] -left-[10%] w-[70%] h-[70%] rounded-full bg-violet-600/30 blur-[130px] animate-pulse" />
                <div className="absolute bottom-[20%] -right-[20%] w-[60%] h-[60%] rounded-full bg-blue-500/20 blur-[120px]" />
            </div>

            <div className="z-10 w-full max-w-md px-8 relative">
                <div className="flex justify-center mb-8">
                    <div className="h-16 w-16 bg-gradient-to-tr from-violet-600 to-cyan-400 rounded-2xl flex items-center justify-center shadow-[0_0_50px_rgba(139,92,246,0.6)]">
                        <Activity className="text-white w-8 h-8" />
                    </div>
                </div>

                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl">
                    <div className="text-center mb-10">
                        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400 mb-2 font-sans tracking-tight">
                            Welcome to Aifya
                        </h1>
                        <p className="text-slate-400 text-sm">
                            Sign in to access your unified healthcare workspace.
                        </p>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-3">
                            <AlertCircle className="w-5 h-5 text-red-400" />
                            <p className="text-sm text-red-400">{error}</p>
                        </div>
                    )}

                    <form className="space-y-6" onSubmit={handleLogin}>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-300 ml-1">Email</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                    <Mail className="h-5 w-5 text-slate-500 group-focus-within:text-violet-400 transition-colors" />
                                </div>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full bg-slate-950 border border-slate-800 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 rounded-xl py-3 pl-11 pr-4 text-slate-200 outline-none transition-all placeholder:text-slate-600"
                                    placeholder="Enter your email"
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <div className="flex justify-between items-center ml-1">
                                <label className="text-sm font-medium text-slate-300">Password</label>
                                <a href="#" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">
                                    Forgot password?
                                </a>
                            </div>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                    <Lock className="h-5 w-5 text-slate-500 group-focus-within:text-violet-400 transition-colors" />
                                </div>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-slate-950 border border-slate-800 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 rounded-xl py-3 pl-11 pr-4 text-slate-200 outline-none transition-all placeholder:text-slate-600"
                                    placeholder="Enter your password"
                                    required
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading}
                            onMouseEnter={() => setIsHovered(true)}
                            onMouseLeave={() => setIsHovered(false)}
                            className="w-full relative overflow-hidden group bg-violet-600 hover:bg-violet-500 disabled:opacity-70 disabled:cursor-not-allowed text-white rounded-xl py-3.5 font-medium transition-all shadow-[0_0_20px_rgba(139,92,246,0.3)] hover:shadow-[0_0_30px_rgba(139,92,246,0.5)] flex items-center justify-center gap-2"
                        >
                            <span className="relative z-10 flex items-center gap-2">
                                {isLoading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        Authenticating...
                                    </>
                                ) : (
                                    <>
                                        Sign In securely
                                        <ArrowRight className={`w-4 h-4 transition-transform duration-300 ${isHovered ? 'translate-x-1' : ''}`} />
                                    </>
                                )}
                            </span>
                            <div className="absolute inset-0 bg-gradient-to-r from-violet-600 to-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-0" />
                        </button>
                    </form>

                    <p className="mt-8 text-center text-xs text-slate-500">
                        Secured by Keycloak Identity Provider
                    </p>
                </div>
            </div>
        </div>
    );
}
