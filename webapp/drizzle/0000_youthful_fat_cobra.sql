CREATE TABLE `accounts` (
	`owner` text PRIMARY KEY NOT NULL,
	`version` integer DEFAULT 0 NOT NULL,
	`state` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `rates` (
	`owner` text NOT NULL,
	`bucket` text NOT NULL,
	`count` integer NOT NULL,
	`reset` integer NOT NULL,
	PRIMARY KEY(`owner`, `bucket`)
);
--> statement-breakpoint
CREATE TABLE `requests` (
	`owner` text NOT NULL,
	`id` text NOT NULL,
	`hash` text NOT NULL,
	`version` integer NOT NULL,
	PRIMARY KEY(`owner`, `id`)
);
