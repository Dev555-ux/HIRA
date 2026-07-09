"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useCreateBusiness } from "@/hooks/use-onboarding";
import { useAuthContext } from "@/lib/auth-context";

const INDUSTRIES = [
  "Dental Clinic",
  "Beauty Salon",
  "Immigration & Study Abroad Consultancy",
  "Gym & Fitness Center",
  "Real Estate Agency",
  "Café / Restaurant",
  "Other",
];

const schema = z.object({
  name: z.string().trim().min(1, "Business name is required"),
  industry: z.string().min(1, "Select what kind of business this is"),
  contactEmail: z
    .string()
    .trim()
    .min(1, "Business email is required")
    .email("Enter a valid email address"),
  country: z.string().optional(),
  timezone: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function OnboardingPage() {
  const router = useRouter();
  const { user } = useAuthContext();
  const { toast } = useToast();
  const createBusiness = useCreateBusiness();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    if (!user?.email) return; // guarded in the UI below; nothing to submit without it
    try {
      await createBusiness.mutateAsync({
        name: values.name,
        owner_email: user.email,
        industry: values.industry,
        contact_email: values.contactEmail,
        country: values.country || undefined,
        timezone: values.timezone || undefined,
      });
      toast({
        title: "You're all set!",
        description: "Let's get your AI receptionist ready.",
        variant: "success",
      });
      router.replace("/dashboard");
    } catch {
      // surfaced below via createBusiness.isError
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>👋 Hi, I&apos;m HIRA</CardTitle>
        <CardDescription>
          Let&apos;s set up your AI receptionist. Tell me a bit about your business.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!user?.email && (
          <p className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            We couldn&apos;t find a verified email on your account — please add one before
            continuing.
          </p>
        )}
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Field label="Business name" error={errors.name?.message}>
            <Input placeholder="Acme Dental Clinic" {...register("name")} />
          </Field>

          <Field label="Industry" error={errors.industry?.message}>
            <Select defaultValue="" {...register("industry")}>
              <option value="" disabled>
                Select one
              </option>
              {INDUSTRIES.map((industry) => (
                <option key={industry} value={industry}>
                  {industry}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Business email" error={errors.contactEmail?.message}>
            <Input type="email" placeholder="hello@acmedental.com" {...register("contactEmail")} />
          </Field>

          <Field label="Country (optional)">
            <Input placeholder="India" {...register("country")} />
          </Field>

          <Field label="Time zone (optional)">
            <Input placeholder="Asia/Kolkata" {...register("timezone")} />
          </Field>

          {createBusiness.isError && (
            <p className="text-sm text-destructive">
              {createBusiness.error instanceof ApiError
                ? createBusiness.error.message
                : "Something went wrong — please try again."}
            </p>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={createBusiness.isPending || !user?.email}
          >
            {createBusiness.isPending ? "Setting up…" : "Continue"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {error && <span className="block text-xs text-destructive">{error}</span>}
    </label>
  );
}
